#ifndef OCPCI_LIB_VFIO_H
#define OCPCI_LIB_VFIO_H

#include <stdint.h>
#include <stdlib.h>
#include <sys/types.h>
#include <stdbool.h>
#include <string.h>
#include <linux/vfio.h>
#include "ocpci_lib.h"

/** \brief The OCPCI device internal structure.
 *
 * Note that the structure name is "struct ocpci_dev_t"
 * but the typedef is "ocpci_dev_h" - the 'h' indicates
 * that it's a handle, and should not be accessed directly
 * but by using accessor functions.
 */
typedef struct ocpci_vfio_dev_t {
  bool valid;
  int container;
  int group;
  int device;

  struct vfio_region_info conf_info;
  struct vfio_region_info bar0_info;
  struct vfio_region_info bar1_info;

  void *bar0;
  void *bar1;
  void *config;
  
  unsigned char *buffer;
  unsigned int size;
  __u64 iova;
} ocpci_vfio_dev_h;

int ocpci_lib_vfio_open(ocpci_vfio_dev_h *dev,
			const char *path);
void ocpci_lib_vfio_close(ocpci_vfio_dev_h *dev);

bool ocpci_vfio_is_open(ocpci_vfio_dev_h *dev);

ocpci_bridge_regs_t *ocpci_lib_vfio_get_bridge_regs(ocpci_vfio_dev_h *dev);
void *ocpci_lib_vfio_get_bar1(ocpci_vfio_dev_h *dev);

uint32_t ocpci_lib_vfio_config_read(ocpci_vfio_dev_h *dev, uint32_t offset, uint32_t size);
int ocpci_lib_vfio_config_write(ocpci_vfio_dev_h *dev, uint32_t offset, uint32_t size, uint32_t val);

unsigned int ocpci_lib_vfio_bar0_read(ocpci_vfio_dev_h *dev, uint32_t offset);
int ocpci_lib_vfio_bar0_write(ocpci_vfio_dev_h *dev, uint32_t offset, unsigned int value);
unsigned int ocpci_lib_vfio_bar1_read(ocpci_vfio_dev_h *dev, uint32_t offset);
int ocpci_lib_vfio_bar1_write(ocpci_vfio_dev_h *dev, uint32_t offset, unsigned int value);

int ocpci_lib_vfio_dma_init(ocpci_vfio_dev_h *dev,
			    __u64 device_base_addr,
			    uint32_t size);
int ocpci_lib_vfio_dma_finish(ocpci_vfio_dev_h *dev);

int ocpci_lib_vfio_dma_init_with_buffer(ocpci_vfio_dev_h *dev,
					__u64 device_base,
					void *buffer,
					uint32_t size);
int ocpci_lib_vfio_dma_finish_with_buffer(ocpci_vfio_dev_h *dev);

int ocpci_lib_vfio_dma_read(ocpci_vfio_dev_h *dev,
			    unsigned char *buffer,
			    uint32_t offset,
			    uint32_t size);

#endif
