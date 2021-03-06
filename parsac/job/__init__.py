from __future__ import print_function
import os.path
import xml.etree.ElementTree

from . import shared
from . import program
from . import gotm
from . import idealized
from . import function

name2class = {'gotm': gotm.Job, 'program': program.Job, 'idealized': idealized.Job, 'function': function.Job}

def fromConfigurationFile(path, **kwargs):
    if not os.path.isfile(path):
        print('Configuration file "%s" not found.' % path)
        return None

    xml_tree = xml.etree.ElementTree.parse(path)

    job_id = os.path.splitext(os.path.basename(path))[0]

    element = xml_tree.find('model')
    if element is not None:
        with shared.XMLAttributes(element, 'the model element') as att:
            model_type = att.get('type')
    else:
        model_type = 'gotm'

    assert model_type in name2class, 'Unknown job type "%s" specified.' % model_type

    return name2class[model_type](job_id, xml_tree, os.path.dirname(path), **kwargs)
