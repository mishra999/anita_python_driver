from distutils.core import setup, Extension
setup(name="ocpci", version="1.0",
      ext_modules=[
          Extension("ocpci",
                    ["ocpci_lib_python.c","ocpci_lib.c"]),
          ])
