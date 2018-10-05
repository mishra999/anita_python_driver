#ifndef OCPCI_LIB_UIO_H
#define OCPCI_LIB_UIO_H

#include <stdint.h>
#include <stdlib.h>
#include <sys/types.h>
#include <stdbool.h>
#include <string.h>
#include "ocpci_lib.h"

/** \brief The OCPCI device internal structure.
 *
 * Note that the structure name is "struct ocpci_dev_t"
 * but the typedef is "ocpci_dev_h" - the 'h' indicates
 * that it's a handle, and should not be accessed directly
 * but by using accessor functions.
 */
typedef struct ocpci_dev_t {
  bool valid;
  size_t wb_size;
  int cfg_fd;
  int bar0_fd;
  int bar1_fd;
  int irq_fd;
  
  void *bar0;
  void *bar1;
  ocpci_bridge_regs_t *bridge;
} ocpci_uio_dev_h;

int ocpci_lib_uio_open(ocpci_uio_dev_h *dev,
		   const char *path,
		   size_t wb_size);
void ocpci_lib_uio_close(ocpci_uio_dev_h *dev);

bool ocpci_uio_is_open(ocpci_uio_dev_h *dev);

ocpci_bridge_regs_t *ocpci_lib_uio_get_bridge_regs(ocpci_uio_dev_h *dev);
void *ocpci_lib_uio_get_bar1(ocpci_uio_dev_h *dev);

unsigned int ocpci_lib_uio_bar0_read(ocpci_uio_dev_h *dev, uint32_t offset);
int ocpci_lib_uio_bar0_write(ocpci_uio_dev_h *dev, uint32_t offset, unsigned int value);
unsigned int ocpci_lib_uio_bar1_read(ocpci_uio_dev_h *dev, uint32_t offset);
int ocpci_lib_uio_bar1_write(ocpci_uio_dev_h *dev, uint32_t offset, unsigned int value);

int ocpci_lib_uio_irq_init(ocpci_uio_dev_h *dev);
int ocpci_lib_uio_irq_wait(ocpci_uio_dev_h *dev);
int ocpci_lib_uio_irq_unmask(ocpci_uio_dev_h *dev);

#endif
