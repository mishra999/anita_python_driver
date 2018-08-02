from distutils.core import setup, Extension
setup(name="ocpci", version="1.0",
      ext_modules=[
          Extension("ocpci_uio",
                    ["ocpci_lib_uio_python.c","ocpci_lib_uio.c"]),
          Extension("ocpci_vfio",
                    ["ocpci_lib_vfio_python.c", "ocpci_lib_vfio.c"])
          ])
