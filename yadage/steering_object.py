import adage
import adage.backends
import os
import json
import workflow_loader
import utils
import visualize
import serialize
import yadageschemas
import logging
from packtivity.statecontexts.posixfs_context import LocalFSProvider, LocalFSState

from controllers import setup_controller_from_statestring
from wflow import YadageWorkflow
from utils import setupbackend_fromstring

log = logging.getLogger(__name__)

class YadageSteering():
    '''
    high level steering object to manage worklfow execution
    '''
    def __init__(self,loggername = __name__):
        self.log = logging.getLogger(loggername)
        self.metadir = None
        self.controller = None
        self.rootprovider = None
        self.initdata = {}
        self.adage_kwargs = {}

    @property
    def workflow(self):
        '''
        :return: the workflow object (from the controller)
        '''
        return self.controller.adageobj

    def prepare_meta(self,metadir,accept=False):
        '''
        prepare workflow meta-data directory

        :param metadir: the meta-data directory name
        '''
        assert metadir
        self.metadir = metadir
        if os.path.exists(self.metadir):
            if not accept:
                raise RuntimeError('yadage meta directory exists. explicitly accept')
        else:
            os.makedirs(self.metadir)
        self.adage_argument(workdir = os.path.join(self.metadir,'adage'))

    def prepare(self, workdir = None, initdata = None, inputarchive = None, initdir = 'init', read = None, accept_existing_metadir = False, metadir = None,  rootprovider = None):
        '''
        prepares initialization data (such as ) and sets up stateprovider used for workflow stages
        if initialization data is provided, it may be mutated to reflect automatic data discovery
        '''
        if workdir:
            self.prepare_meta(metadir or '{}/_yadage/'.format(workdir), accept_existing_metadir)
            initdir = os.path.join(workdir,initdir)
            if inputarchive:
                initdir = utils.prepare_workdir_from_archive(initdir, inputarchive)
            if initdata:
                utils.discover_initfiles(initdata,os.path.realpath(initdir))
            writable_state    = LocalFSState([workdir])
            self.rootprovider = LocalFSProvider(read,writable_state, ensure = True, nest = True)
        elif rootprovider:
            self.prepare_meta(metadir)
            self.rootprovider = rootprovider
        else:
            raise RuntimeError('must provide local work directory or root state provider')
        
    def init_workflow(self, workflow, initdata = None, toplevel = os.getcwd(), statesetup = 'inmem', validate = True, schemadir = yadageschemas.schemadir):
        '''
        load workflow from spec and initialize it
        
        :param workflow: the workflow spec source
        :param toplevel: base URI against which to resolve JSON references in the spec
        :param initdata: initialization data for workflow 
        '''
        workflow_json = workflow_loader.workflow(
            workflow,
            toplevel=toplevel,
            schemadir=schemadir,
            validate=validate
        )
        with open('{}/yadage_template.json'.format(self.metadir), 'w') as f:
            json.dump(workflow_json, f)
        workflowobj = YadageWorkflow.createFromJSON(workflow_json, self.rootprovider)
        if initdata:
            log.info('initializing workflow with %s',initdata)
            workflowobj.view().init(initdata)
        else:
            log.info('no initialization data')
        self.controller = setup_controller_from_statestring(workflowobj, statestr = statesetup)

    def adage_argument(self,**kwargs):
        '''
        add keyword arguments for workflow execution (adage)
        :param kwargs: adage keyword arguments (see adage documentation for options)
        '''
        self.adage_kwargs.update(**kwargs)

    def run_adage(self, backend = setupbackend_fromstring('multiproc:auto'), **adage_kwargs):
        '''
        execution workflow with adage based against given backend
        '''
        self.controller.backend = backend
        self.adage_argument(**adage_kwargs)
        adage.rundag(controller = self.controller, **self.adage_kwargs)

    def serialize(self):
        '''
        serialized workflow and backend states (stored in meta directory)
        '''
        serialize.snapshot(
            self.workflow,
            '{}/yadage_snapshot_workflow.json'.format(self.metadir),
            '{}/yadage_snapshot_backend.json'.format(self.metadir)
        )

    def visualize(self):
        '''
        generate workflow visualization (stored in meta directory)
        '''
        visualize.write_prov_graph(self.metadir, self.workflow, vizformat='png')
        visualize.write_prov_graph(self.metadir, self.workflow, vizformat='pdf')

