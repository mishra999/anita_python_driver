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

const char *config_path = "/device/config";
const char *resource0_path = "/device/resource0";
const char *resource1_path = "/device/resource1";

bool ocpci_vfio_is_open(ocpci_vfio_dev_h *dev) {
  return dev->valid;
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
  close(dev->device);
  close(dev->group);
  close(dev->container);
}
