#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/stat.h>
#include <stdbool.h>
#include <libgen.h>

#include "ocpci_lib_vfio.h"

#define OCPCI_BAR_SIZE 4096

bool ocpci_vfio_is_open(ocpci_vfio_dev_h *dev) {
  return dev->valid;
}

// Creates DMA buffer. This includes the mmap.
int ocpci_lib_vfio_dma_init(ocpci_vfio_dev_h *dev,
			    __u64 device_base_addr,
			    uint32_t size) {
  int ret;
  struct vfio_iommu_type1_dma_map dma_map = {
    .argsz = sizeof(dma_map)
  };
  if (dev->size) {
    fprintf(stderr, "ocpci_lib_vfio_dma_init: DMA buffer (size %d) already exists\n", size);
    return OCPCI_ERR_DMA;
  }
  if (!size) return OCPCI_SUCCESS;
  
  dev->buffer = mmap(NULL, size, PROT_READ | PROT_WRITE,
		     MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  if (dev->buffer == MAP_FAILED) {
    fprintf(stderr, "ocpci_lib_vfio_dma_init: Failed to map memory of size %d (%s)\n", size, strerror(errno));
    return OCPCI_ERR_MEM;
  }
  ret = madvise(dev->buffer, dev->size, MADV_HUGEPAGE);
  if (ret) {
    fprintf(stderr, "ocpci_lib_vfio_dma_init: Failed to madvise memory (%s)\n", strerror(errno));
    munmap(dev->buffer, dev->size);
    return OCPCI_ERR_MEM;
  }
  ret = ocpci_lib_vfio_dma_init_with_buffer(dev, device_base_addr, dev->buffer, size);
  if (ret) {
    munmap(dev->buffer, size);
  }
  return ret;
}

int ocpci_lib_vfio_dma_enabled(ocpci_vfio_dev_h *dev) {
  if (dev->size) return 1;
  else return 0;
}

__u64 ocpci_lib_vfio_dma_base(ocpci_vfio_dev_h *dev) {
  return dev->iova;
}

int ocpci_lib_vfio_dma_init_with_buffer(ocpci_vfio_dev_h *dev,
					__u64 device_base,
					void *buffer,
					uint32_t size) {
  int ret;
  uint16_t val;
  struct vfio_iommu_type1_dma_map dma_map = {
    .argsz = sizeof(dma_map)
  };
  if (!size) return OCPCI_SUCCESS;

  // Enable bus mastering on the device.
#define PCI_COMMAND 0x04
#define PCI_COMMAND_MASTER 0x4
  val = ocpci_lib_vfio_config_read(dev, PCI_COMMAND, 2);
  val = val | PCI_COMMAND_MASTER;
  ret = ocpci_lib_vfio_config_write(dev, PCI_COMMAND, 2, val);
  if (ret) {
    fprintf(stderr, "ocpci_lib_vfio_dma_init: Failed to enable bus mastering (%s)\n", strerror(errno));
    return OCPCI_ERR_DMA;
  }

  dev->buffer = buffer;
  dev->size = size;
  dev->iova = device_base;
  
  dma_map.vaddr = dev->buffer;
  dma_map.size = dev->size;
  dma_map.flags = VFIO_DMA_MAP_FLAG_READ | VFIO_DMA_MAP_FLAG_WRITE;
  dma_map.iova = device_base;
  ret = ioctl(dev->container, VFIO_IOMMU_MAP_DMA, &dma_map);
  if (ret) {
    fprintf(stderr, "ocpci_lib_vfio_dma_init: Failed to DMA map buffer (%s)\n", strerror(errno));
    dev->size = 0;
    return OCPCI_ERR_DMA;
  }
  return OCPCI_SUCCESS;
}

int ocpci_lib_vfio_dma_finish(ocpci_vfio_dev_h *dev) {
  int ret;
  if (!dev->size) return OCPCI_SUCCESS;
  ret = ocpci_lib_vfio_dma_finish_with_buffer(dev);
  if (ret) return ret;
  munmap(dev->buffer, dev->size);
  return OCPCI_SUCCESS;
}

// Destroys DMA buffer.
int ocpci_lib_vfio_dma_finish_with_buffer(ocpci_vfio_dev_h *dev) {
  struct vfio_iommu_type1_dma_unmap dma_unmap = {
    .argsz = sizeof(dma_unmap)
  };
  int ret;
  int val;
  
  if (!dev->size) return OCPCI_SUCCESS;
  dma_unmap.iova = dev->iova;
  dma_unmap.size = dev->size;
  ret = ioctl(dev->container, VFIO_IOMMU_UNMAP_DMA, &dma_unmap);
  if (ret) {
    fprintf(stderr, "ocpci_lib_vfio_dma_finish: Failed to unmap DMA buffer (%s)\n", strerror(errno));
    return OCPCI_ERR_DMA;
  }
  dev->size = 0;
  // Disable bus mastering
  val = ocpci_lib_vfio_config_read(dev, PCI_COMMAND, 2);
  val = val & ~PCI_COMMAND_MASTER;
  ret = ocpci_lib_vfio_config_write(dev, PCI_COMMAND, 2, val);
  if (ret) {
    fprintf(stderr, "ocpci_lib_vfio_dma_finish: Failed to disable bus mastering (%s)\n", strerror(errno));
    return OCPCI_ERR_DMA;
  }
  return OCPCI_SUCCESS;
}

// *Copies* data from the DMA buffer into the user buffer
int ocpci_lib_vfio_dma_read(ocpci_vfio_dev_h *dev,
				       unsigned char *buffer,
				       uint32_t offset,
				       uint32_t size) {
  if (!dev->size) return OCPCI_ERR_DMA_OVERRUN;
  if (offset+size > dev->size) {
    fprintf(stderr, "ocpci_lib_vfio_dma_read: read %d bytes at %d would overflow (%d bytes)\n",
	    offset,
	    size,
	    dev->size);
    return OCPCI_ERR_DMA_OVERRUN;
  }
  memcpy(buffer, ((unsigned char *) dev->buffer) + offset, size);
  return OCPCI_SUCCESS;
}

// Config space access. Byte by byte for now.
uint32_t ocpci_lib_vfio_config_read(ocpci_vfio_dev_h *dev, uint32_t offset, uint32_t size) {
  int ret;
  uint32_t val;
  switch(size) {
  case 0: return OCPCI_SUCCESS;
  case 1: break;
  case 2: if (offset & 0x1) goto unaligned_config_read; break;
  case 4: if (offset & 0x3) goto unaligned_config_read; break;
  default: fprintf(stderr, "ocpci_lib_vfio_config_read: unknown read size %d\n", size); return OCPCI_ERR_INVALID_REGISTER;
  }
  
  ret = pread(dev->device, &val, size, dev->conf_info.offset + offset);
  if (ret < 0) {
    fprintf(stderr, "ocpci_lib_vfio_config_read: error reading (%s)\n", strerror(errno));
    return OCPCI_ERR_INVALID_REGISTER;
  }
  return val;

 unaligned_config_read:
  fprintf(stderr, "ocpci_lib_vfio_config_read: unaligned config read of %d bytes from %2.2x\n", size, offset);
  return OCPCI_ERR_INVALID_REGISTER;
}

int ocpci_lib_vfio_config_write(ocpci_vfio_dev_h *dev, uint32_t offset, uint32_t size, uint32_t val) {
  int ret;
  switch(size) {
  case 0: return OCPCI_SUCCESS;
  case 1: break;
  case 2: if (offset & 0x1) goto unaligned_config_write; break;
  case 4: if (offset & 0x3) goto unaligned_config_write; break;
  default: fprintf(stderr, "ocpci_lib_vfio_config_write: unknown write size %d\n", size); return OCPCI_ERR_INVALID_REGISTER;
  }

  ret = pwrite(dev->device, &val, size, dev->conf_info.offset + offset);
  if (ret < 0) {
    fprintf(stderr, "ocpci_lib_vfio_config_write: error writing (%s)\n", strerror(errno));
    return OCPCI_ERR_INVALID_REGISTER;
  }
  return OCPCI_SUCCESS;

 unaligned_config_write:
  fprintf(stderr, "ocpci_lib_vfio_config_write: unaligned config write of %d bytes from %2.2x\n", size, offset);
  return OCPCI_ERR_INVALID_REGISTER;
}
  

unsigned int ocpci_lib_vfio_bar1_read(ocpci_vfio_dev_h *dev, uint32_t offset) {
  uint32_t mod_offset;
  uint32_t *p;
  uint32_t val;
  if (!dev) return -1;
  if (offset > dev->bar1_info.size) return -1;
  if (offset & 0x3) {
    fprintf(stderr, "ocpci_lib_vfio_bar1_read: warning - non-integer aligned read of 0x%8.8x\n", offset);
  }
  mod_offset = offset >> 2;
  p = (uint32_t *) dev->bar1;
  val = *(p + mod_offset);  
  return val;
}

int ocpci_lib_vfio_bar1_write(ocpci_vfio_dev_h *dev, uint32_t offset, unsigned int value) {
  uint32_t mod_offset;
  uint32_t *p;
  if (!dev) return OCPCI_ERR_INVALID_HANDLE;
  if (offset > dev->bar1_info.size) return OCPCI_ERR_INVALID_REGISTER;
  if (offset & 0x3) {
    fprintf(stderr, "ocpci_lib_vfio_bar1_read: warning - non-integer aligned read of 0x%8.8x\n", offset);
  }
  mod_offset = offset >> 2;
  p = (uint32_t *) dev->bar1;
  *(p + mod_offset) = value;
  return OCPCI_SUCCESS;
}

int ocpci_lib_vfio_open(ocpci_vfio_dev_h *dev,
		   const char *devstr) {
  char path[50], iommu_group_path[50];
  char *group_name;
  size_t pathlen;
  struct stat st;
  struct vfio_group_status group_status = {
    .argsz = sizeof(struct vfio_group_status),
  };
  int ret;
  int len;
  int groupid;
  
  if (!dev) return OCPCI_ERR_INVALID_HANDLE;
  dev->valid = 0;
  dev->size = 0;
  pathlen = strlen(path);

  dev->container = open("/dev/vfio/vfio", O_RDWR);
  if (dev->container < 0) {
    perror("ocpci_lib_vfio_open: Failed to open /dev/vfio/vfio");
    return OCPCI_ERR_OPEN;
  }
  snprintf(path, sizeof(path), "/sys/bus/pci/devices/%s/", devstr);
  ret = stat(path, &st);
  if (ret < 0) {
    printf("ocpci_lib_vfio_open: No such device");
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  strncat(path, "iommu_group", sizeof(path)-strlen(path)-1);
  len = readlink(path, iommu_group_path, sizeof(iommu_group_path));
  if (len<=0) {
    printf("ocpci_lib_vfio_open: no iommu_group for device\n");
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  iommu_group_path[len] = 0;
  group_name=basename(iommu_group_path);
  if (sscanf(group_name,"%d", &groupid) != 1) {
    printf("ocpci_lib_vfio_open: unknown group\n");
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  // Find out if the group is viable.
  snprintf(path, sizeof(path), "/dev/vfio/%d", groupid);
  dev->group = open(path, O_RDWR);
  if (dev->group < 0) {
    perror("ocpci_lib_vfio_open: failed to open group");
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  // Get the group status...
  ret = ioctl(dev->group, VFIO_GROUP_GET_STATUS, &group_status);
  if (ret) {
    perror("ocpci_lib_vfio_open: failed to get group status");
    close(dev->group);
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  if (!group_status.flags & VFIO_GROUP_FLAGS_VIABLE) {
    printf("ocpci_lib_vfio_open: group not viable (check that all devices assigned to vfio)\n");
    close(dev->group);
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  ret = ioctl(dev->group, VFIO_GROUP_SET_CONTAINER, &dev->container);
  if (ret) {
    perror("ocpci_lib_vfio_open: failed to set group container");
    close(dev->group);
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  ret = ioctl(dev->container, VFIO_SET_IOMMU, VFIO_TYPE1v2_IOMMU);
  if (ret) {
    perror("ocpci_lib_vfio_open: failed to set IOMMU\n");
    close(dev->group);
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  // now fetch the actual device
  dev->device = ioctl(dev->group, VFIO_GROUP_GET_DEVICE_FD, devstr);
  if (dev->device < 0) {
    printf("ocpci_lib_vfio_open: failed to get device\n");
    close(dev->group);
    return OCPCI_ERR_OPEN;
  }
  // Get the region info. Config space doesn't support MMAP.
  dev->conf_info.index = VFIO_PCI_CONFIG_REGION_INDEX;
  dev->conf_info.argsz = sizeof(dev->conf_info);
  if (ioctl(dev->device, VFIO_DEVICE_GET_REGION_INFO, &dev->conf_info)) {
    printf("ocpci_lib_vfio_open: failed to get region info for CONFIG\n");
    close(dev->device);
    close(dev->group);
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  // Can't MMAP it. To write/read from it, we have to use the offset and pread.
  
  // BAR0 is the PCI bridge configuration registers.
  dev->bar0_info.index=0;
  dev->bar0_info.argsz=sizeof(dev->bar0_info);
  if (ioctl(dev->device, VFIO_DEVICE_GET_REGION_INFO, &dev->bar0_info)) {
    printf("ocpci_lib_vfio_open: failed to get region info for BAR0\n");
    close(dev->device);
    close(dev->group);
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  if (!(dev->bar0_info.flags & VFIO_REGION_INFO_FLAG_MMAP)) {
    printf("ocpci_lib_vfio_open: BAR0 region is not MMAP-able\n");
    return OCPCI_ERR_OPEN;
  }
  dev->bar0 = mmap(NULL, (size_t) dev->bar0_info.size,
		   PROT_READ | PROT_WRITE, 
		   MAP_SHARED,
		   dev->device, (off_t) dev->bar0_info.offset);
  if (dev->bar0 == MAP_FAILED) {
    printf("ocpci_lib_vfio_open: mmap BAR0 failed\n");
    close(dev->device);
    close(dev->group);
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  // BAR1 is the WISHBONE space.
  dev->bar1_info.index=1;
  dev->bar1_info.argsz=sizeof(dev->bar1_info);
  if (ioctl(dev->device, VFIO_DEVICE_GET_REGION_INFO, &dev->bar1_info)) {
    printf("ocpci_lib_vfio_open: failed to get region info for BAR1\n");
    munmap(dev->bar0, dev->bar0_info.size);
    close(dev->device);
    close(dev->group);
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  if (!(dev->bar1_info.flags & VFIO_REGION_INFO_FLAG_MMAP)) {
    printf("ocpci_lib_vfio_open: BAR1 region is not MMAP-able\n");
    munmap(dev->bar0, dev->bar0_info.size);
    close(dev->device);
    close(dev->group);
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  dev->bar1 = mmap(NULL, (size_t) dev->bar1_info.size,
		   PROT_READ | PROT_WRITE, 
		   MAP_SHARED,
		   dev->device, (off_t) dev->bar1_info.offset);
  if (dev->bar1 == MAP_FAILED) {
    printf("ocpci_lib_vfio_open: mmap BAR1 failed\n");
    munmap(dev->bar0, dev->bar0_info.size);
    close(dev->device);
    close(dev->group);
    close(dev->container);
    return OCPCI_ERR_OPEN;
  }
  dev->valid = 1;
  return OCPCI_SUCCESS;
}

void ocpci_lib_vfio_close(ocpci_vfio_dev_h *dev) {
  if (!dev) return;
  if (!dev->valid) return;   
  munmap(dev->bar0, dev->bar0_info.size);
  munmap(dev->bar1, dev->bar1_info.size);
  if (dev->size) ocpci_lib_vfio_dma_finish_with_buffer(dev);
  close(dev->device);
  close(dev->group);
  close(dev->container);
}
