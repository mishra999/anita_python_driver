#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>
#include <stdint.h>
#include <Python.h>
#include <structmember.h>

#include "ocpci_lib.h"

typedef struct {
  PyObject_HEAD
  ocpci_dev_h dev;
} ocpci_Device;

static PyObject *
ocpci_Device_read(ocpci_Device *self, PyObject *args) {
  // passed 1 integer 
  uint32_t offset;
  uint32_t val;
  if (!PyArg_ParseTuple(args, "I", &offset)) return NULL;
  val = ocpci_lib_bar1_read(&self->dev, offset);
  return Py_BuildValue("i", val);
}

static PyObject *
ocpci_Device_write(ocpci_Device *self, PyObject *args) {
  // passed 2 integers: address and value to write.
  uint32_t offset;
  uint32_t value;
  if (!PyArg_ParseTuple(args, "II",
			&offset, &value))
    return NULL;  
  if (ocpci_lib_bar1_write(&self->dev, offset, value)) {
    PyErr_SetString(PyExc_ValueError,"Illegal offset");
    return NULL;
  }
  Py_RETURN_NONE;
}

static PyMemberDef ocpci_Device_members[] = {
  { NULL } /* Sentinel */
};

static PyMethodDef ocpci_Device_methods[] = {
  { "read", (PyCFunction) ocpci_Device_read, METH_VARARGS,
    "Read from a WISHBONE address behind the OpenCores PCI Bridge."},
  { "write", (PyCFunction) ocpci_Device_write, METH_VARARGS,
    "Write to a WISHBONE address behind the OpenCores PCI Bridge."},
  { NULL } /* Sentinel */
};

static void
ocpci_Device_dealloc(ocpci_Device *self)
{
  if (ocpci_is_open(&self->dev)) ocpci_lib_close(&self->dev);  
  self->ob_type->tp_free((PyObject*) self);
}

static PyObject *
ocpci_Device_new( PyTypeObject *type, PyObject *args, PyObject *kwds) {
  ocpci_Device *self;
  self = (ocpci_Device *) type->tp_alloc(type, 0);
  return (PyObject *) self;
}

// Default path.
const char *ocpci_Device_path_default = "/sys/class/uio/uio0";
// Default size (8 MiB).
const uint32_t ocpci_Device_wb_size_default = 8*1024*1024;

static int
ocpci_Device_init( ocpci_Device *self, PyObject *args, PyObject *kwds) {
  static char *kwlist[] = {"path","wb_size",NULL};
  const char *path;
  uint32_t wb_size;
  path = ocpci_Device_path_default;
  wb_size = ocpci_Device_wb_size_default;

  if (!PyArg_ParseTupleAndKeywords(args, kwds, "|sI", kwlist,
				   &path, &wb_size)) return -1;
  if (ocpci_lib_open(&self->dev, path, wb_size)) return -1;
  return 0;
}

static PyTypeObject ocpci_DeviceType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "ocpci.Device",            /*tp_name*/
    sizeof(ocpci_Device),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor) ocpci_Device_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "OCPCI Devices",           /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    ocpci_Device_methods,      /* tp_methods */
    ocpci_Device_members,      /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)ocpci_Device_init,      /* tp_init */
    0,                         /* tp_alloc */
    ocpci_Device_new,          /* tp_new */
};


static PyMethodDef module_methods[] = {
  {NULL} /* Sentinel */
};

#ifndef PyMODINIT_FUNC
#define PyMODINIT_FUNC void
#endif

PyMODINIT_FUNC
initocpci(void)
{
  PyObject *m;
  if (PyType_Ready(&ocpci_DeviceType) < 0) 
    return;

  m = Py_InitModule3("ocpci", module_methods,
		     "OpenCores PCI Bridge library.");
  
  if (m == NULL) 
    return;
  
  Py_INCREF(&ocpci_DeviceType);
  PyModule_AddObject(m, "Device", (PyObject *) &ocpci_DeviceType);
}
