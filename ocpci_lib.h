#ifndef OCPCI_LIB_H
#define OCPCI_LIB_H

#define OCPCI_SUCCESS 0
#define OCPCI_ERR_INVALID_HANDLE -1
#define OCPCI_ERR_OPEN -2
#define OCPCI_ERR_INVALID_REGISTER -3
#define OCPCI_ERR_MEM -4
#define OCPCI_ERR_UNALIGNED_WRITE -5
#define OCPCI_ERR_NO_DMA -6
#define OCPCI_ERR_DMA -7
#define OCPCI_ERR_DMA_OVERRUN -8

#define PCI_CONFIGURATION_SIZE 256

typedef struct ocpci_image_regs_t {
  uint32_t IMG_CTRL;
  uint32_t BA;
  uint32_t AM;
  uint32_t TA;
} ocpci_image_regs_t;

typedef struct ocpci_bridge_regs_t {
  uint8_t configuration[PCI_CONFIGURATION_SIZE];
  ocpci_image_regs_t P_Image[5];
  uint32_t P_ERR_CS;
  uint32_t P_ERR_ADDR;
  uint32_t P_ERR_DATA;
  // 16C-17F are unused (20 bytes)
  uint8_t gap0[20];
  ocpci_image_regs_t W_Image[5];
  uint32_t W_ERR_CS;
  uint32_t W_ERR_ADDR;
  uint32_t W_ERR_DATA;
  uint32_t CNF_ADDR;
  uint32_t CNF_DATA;
  uint32_t INT_ACK;
  uint32_t ICR;
  uint32_t ISR;
} ocpci_bridge_regs_t;

#endif
