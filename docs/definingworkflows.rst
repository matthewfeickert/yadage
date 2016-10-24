Defining Workflows
==================================

Introduction
------------

Workflows are defined through JSON documents that adhere to a set of defined JSON schemas. To aid legibility they can also be written as YAML documents, as it is a superset of JSON. The YAML loader of the yadage engine also supports a number of shorthands that map 1<->1 to a more verbose version (notably in the stage definitions) and fill in default values when they are not present. We will be using the YAML way of writing the workflow specs throughout these documents.

Basic Terminology
-----------------

Packtivities:
`````````````

The atomic unit of the workflow is a `packtivity` -- a packaged activity. It represents a single parametrized processing step. The parameters a passed as JSON documents and the processing step is executed using one of multiple backends. After processing the packtivity publishes JSON data that includes relevant data for further processing (e.g. referencing files that were created during the processing).

Stages:
```````

Instead of describing a specific graph of tasks, a yadage workflow definition consists of a collection of `stages` that describe how an existing graph should be extended with additional nodes and edges. Starting from an empty graph (0 nodes, 0 edges), it is built up sequentially through application of these stages.

A stage consists of two pieces

1. A stage body (i.e. its scheduler):

  This section describes the logic how to define new nodes (i.e. packtivities with a specific parameter input) and new edges to attach them to the existing graph. Currently yadage supports two stages, one defining a single node and defining multiple nodes, both of which add edges according to the the data accessed from upstream nodes.

2. A predicate (i.e. its dependencies):

  The predicate (also referred to as the stages' dependencies) is a description of when the stage body is ready to be applied. Currently yadage supports a single predicate that takes a number of `JSON Path`_ expressions. Each expression selects a number of stages. The dependency is considered satisfied when all packtivities associated to that stage (i.e. nodes) have a published result.

.. _`JSON Path`: http://goessner.net/articles/JsonPath/

Using JSON references
`````````````````````

Writing the entire workflow in a single file is both cumbersome and limits re-usability of individual components (e.g. for packtivities used in multiple workflows).

During loading each workflow spec is intepreted  with respect to a `toplevel` address. If the workflow contains `JSON references`_ they are resolved with respect to that toplevel URL.

.. _`JSON references`: https://tools.ietf.org/id/draft-pbryan-zyp-json-ref-03.html

Example
.........

In this example stage (details on how to define a stage will be explained below), the packtivity to be scheduled by this stage is referenced using :code:`{$ref: 'steps.yml#/pythia'}` ::

  name: pythia
  dependencies: ['init']
  scheduler:
    scheduler_type: singlestep-stage
    step: {$ref: 'steps.yml#/pythia'}
    parameters:
      settings_file: /analysis/mainPythiaMLM.cmnd
      hepmcfile: '{workdir}/outputfile.hepmc'
      lhefile: {stages: init, output: lhefile}

Assuming that this stage definition is part of an workflow stored at :code:`http://www.example.com/sub/path/workflow.yml`, yadage will look at the same parent location (:code:`http://www.example.com/sub/path`) to look for resource named :code:`http://www.example.com/sub/path/steps.yml`, load it and return the JSON tree under the :code:`pythia` property. The :code:`steps.yml` file could e.g. contain (again details on defining packtivities can be found below)::

  pythia:
    process:
      process_type: 'string-interpolated-cmd'
      cmd: '/analysis/pythia_main/example_main {settings_file} {hepmcfile} {lhefile}'
    publisher:
      publisher_type: 'frompar-pub'
      outputmap:
        hepmcfile: hepmcfile
    environment:
      environment_type: 'docker-encapsulated'
      image: 'lukasheinrich/higgs-mc-studies'

Defining a Packtivity
---------------------

A packtivity represents a parametrized task/activity description with "batteries included", i.e. with full information about the environment and expected result data, such that ideally it can be reproduced on a generic computing resource that is not tailored to that activity.

To define such a packageed activity, one needs to define three pieces of information:

1. A parametrized task description, such as a templated command line string
2. A environment description. This should be as complete as possible and ideally deployable on a diverse set of resources. We will be mainly using Docker images.
3. A result extraction spec that describes how to extract the relevant data fragments after the task has completed. An example is extracting a set of filenames from a work directory or from the original parameters. Currently yadage supports a number of definition schemas for each of these pieces

Process Definitions
```````````````````

1. string interpolated Command Lines

  The simplest process description is a command line string with one or more placeholders. This description assumes python-style placeholders and interpolation algorithms. The placeholders will be matched to the parameters associated to a gien packtivity instance.

  Example::

    process:
      process_type: 'string-interpolated-cmd'
      cmd: '/path/to/binary {input_file} {output_file}'

  for a parameter set such as the following::

    {
      "input_file": "/a/path/to/an/input_file.txt",
      "input_file": "/a/path/to/an/output_file.txt"
    }

  This will result in the following command line string::

    /path/to/binary /a/path/to/an/input_file.txt /a/path/to/an/output_file.txt


  Handling of Arrays: besides plain old data types (PoD) supported by JSON (i.e. strings, boolean, numbers, null) that will be coerced into strings, this process definition converts arrays to space-delimited string sequences. This makes it easy to pass a number of positional arguments to a command line::

    process:
      process_type: 'string-interpolated-cmd'
      cmd: 'cat {inputfiles} > {outputfile}'

  with a parameter set::

    {
      "inputfiles": ["fileA","fileB","fileC"],
      "outputfile": "outputfile"
    }

  will be interpolated as::

    cat fileA fileB fileC > outputfile

2. interpolated interpreted scripts.

  Sometimes the environment does not have completely wrapped command line programs that completely wrap the task at hand, but need a more than a single command to correctly run the task. Therefore another process environment used frequently is the interpolated script process, in which a multi-statement script is interpolated by the parameters (similar to the process), and then is interpreted by the backend using a specified interpreter (the default being :code:`sh`).

  In YAML, the script in conveniently defined using block notation. This is how one would defined a basic shell script to convert all lower case letters of a input file (a parameter) into upper case letters and write the result to an output file.

  .. code-block:: shell

    process_type: 'interpolated-script-cmd'
    script: |
      echo This is again some prose....
      echo "Let's show the environment"
      env
      echo "finally let's just copy the file but with upper case"
      cat {infile} | tr '[:lower:]' '[:upper:]' > {outputfile}


  The interpreter can be specified under the :code:`interpreter` property. For example one could use python

  .. code-block:: python

    process_type: 'interpolated-script-cmd'
    interpreter: python
    script: |
      print 'Hello from Python'
      with open('{infile}') as input:
        with open('{outputfile}','w') as  output:
          output.write(input.read().upper())

  or even the C++ interpreter cling via ROOT

  .. code-block:: text

    process_type: 'interpolated-script-cmd'
    interpreter: root -b
    script: |
      #include <iostream>
      #include <fstream>
      {{
        std::ifstream t("{infile}");
        std::string str((std::istreambuf_iterator<char>(t)),
                         std::istreambuf_iterator<char>());
        std::cout << str << std::endl;
        TString tstring(str.c_str());
        tstring.ToUpper();
        TCanvas c1;
        TH1F h("hist",tstring.Data(),100,-5,5);
        h.FillRandom("gaus",5000);
        h.Draw();
        c1.SaveAs("{outputfile}");
        return 0;
      }}

  In languages (such as C++ as in the example above) that use braces, one must take care to escape them properly using doubling (:code:`{{` and :code:`}}`) in order to not interfere with the interpolation.

Environment Definitions
```````````````````````

  The most commonly used environment description is one that uses Docker Images.


Publisher Definitions
`````````````````````


Defining a Stage
----------------

As explained above, a stage is defined by a predicate and a scheduler. The generic structure of a stage definition is::

  name: <stage name>
  dependencies: <predicate definition>
  scheduler: <scheduler definition>

Predicate Definitions
`````````````````````

Currently a single type of predicate is supported based on JSON path expressions. In a YAML description (which internally uniquely maps to a more verbose JSON definition), it's enought to 


Scheduler Definitions
`````````````````````

Currenty yadage supports two schedulers:

1. a singlestep stage, scheduling a single packtivity with a specific parameter set
2. a multistep stage, scheduling a number of instances of the same packtivity but with different parameters each. A number of ways to build the parameter sets are supported.




Composition using Subworkflows
------------------------------


Validating Workflows
--------------------


Dumping Workflow JSON
---------------------