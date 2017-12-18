from contextlib import contextmanager
import logging
import importlib
import yadageschemas
import os

from .steering_object import YadageSteering
from .utils import setupbackend_fromstring
from .interactive import interactive_deciders

log = logging.getLogger(__name__)

def run_workflow(*args, **kwargs):
    '''
    convenience function around steering context, when no additional settings
    are desired.
    '''
    with steering_ctx(*args, **kwargs):
        pass

def execute_steering(
    steering_object,
    updateinterval = 0.02,
    loginterval = 30,
    default_trackers=True,
    interactive = False,
    backend = None,
    cache = None
    ):

    ys = steering_object
    ys.adage_argument(
        default_trackers = default_trackers,
        trackevery = loginterval,
        update_interval = updateinterval,
    )

    backend = backend or setupbackend_fromstring('multiproc:auto')
    log.info('running yadage workflow on backend %s', backend)
    if cache:
        if cache == 'checksums':
            backend.enable_cache(':'.join([cache,os.path.join(ys.metadir,'cache.json')]))
        else:
            backend.enable_cache(cache)


    custom_tracker = os.environ.get('YADAGE_CUSTOM_TRACKER',None)
    if custom_tracker:
        modulename,trackerclassname = custom_tracker.split(':')
        module = importlib.import_module(modulename)
        trackerclass = getattr(module,trackerclassname)
        ys.adage_argument(additional_trackers = [trackerclass()])

    if interactive:
        extend, submit = interactive_deciders()
        ys.adage_argument(
            extend_decider = extend,
            submit_decider = submit
        )

    ys.run_adage(backend)

@contextmanager
def steering_ctx(
    dataarg,
    workflow = None,
    initdata = None,
    toplevel = os.getcwd(),
    backend = None,
    controller = 'frommodel',
    ctrlopts = None,
    workflow_json = None,
    cache = None,
    dataopts = None,
    updateinterval = 0.02,
    loginterval = 30,
    schemadir = yadageschemas.schemadir,
    metadir = None,
    interactive=False,
    validate=True,
    visualize=True,
    accept_metadir = False,
    modelsetup = 'inmem',
    modelopts = None
):

    ys = YadageSteering.create(
        metadir = metadir, accept_metadir = True if (accept_metadir or cache) else False,
        dataarg = dataarg, dataopts = dataopts,
        workflow_json = workflow_json,
        workflow = workflow, toplevel = toplevel,
        schemadir = schemadir, validate = validate,
        initdata = initdata,
        modelsetup = modelsetup, modelopts = modelopts,
        controller = controller, ctrlopts = ctrlopts,
    )

    yield ys

    try:
        execute_steering(
            steering_object = ys,
            updateinterval = updateinterval,
            loginterval = loginterval,
            default_trackers = visualize,
            interactive = interactive,
            backend = backend,
            cache = cache
        )
    finally:
        ys.serialize()
    if visualize:
        ys.visualize()
