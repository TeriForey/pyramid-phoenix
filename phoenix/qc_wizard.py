
import logging
logger = logging.getLogger(__name__)
from pyramid.view import view_config
from pyramid.security import authenticated_userid
from .models import user_token, add_job
from pyramid.httpexceptions import HTTPFound
from wps import get_wps
from .helpers import wps_url
import os
#TODO: Put constants into a config file
QCDIR = "/home/tk/sandbox/test/climdapssplit/malleefowl/var/qc_cache"
EXAMPLEDATADIR = "/home/tk/sandbox/test/climdapssplit/malleefowl/examples/data/CORDEX"
WPS_SERVICE = "http://localhost:8090/wps"
@view_config(route_name='qc_wizard_check',
             renderer='templates/qc_wizard.pt',
             layout='default',
             permission='edit',
             )
def qc_wizard_check(request):
    title = "Quality Control Wizard"
    user_id = authenticated_userid(request)
    token = user_token(request, user_id)
    
    parallel_id_help = ("An identifier used to avoid processes running on the same directory." + 
                        " Using an existing one will remove all data inside its work directory.")
    parallel_ids = get_parallel_ids(user_id)
    if parallel_ids == []:
        parallel_id_help += " There are currently no existing Parallel IDs."
    else:
        parallel_id_help += " The existing Parallel IDs are:<br>" +", ".join(parallel_ids)
    qc_select_help = ("Comma separated list of parts of the path. If at least one of the elements " +
                      "in the list matches with a path in the data directory, its nc files are " + 
                      "added to the check. It is recommended to put variables into '/' to avoid " +
                      "accidental matches with other path elements. The first element of the path " + 
                      "does not start with a '/' and the last element does not end with a '/'. The " +
                      "wildcard '.*' should be used with care, as the handling of '/' is " + 
                      "considered undefined. (Assuming the paths exist a valid example is: " +
                      "AFR-44/.*/tas, EUR.*, /fx/)")
    qc_lock_help = ("Works similar to select, but prevents the given paths being added. " +
                    "Lock is stronger than select. (e.g. select tas and lock AFR-44 checks all "+
                    "tas that are not in AFR-44.)")

    #a field in fields must contain text, id and value. The entry help is optional.
    #allowed_values can be used if a limited number of possibile values should be available.
    #In that case value will be used as default if it is in allowed_values.
    #For type "checkbox" the existence of the "checked" key will lead to the checkbox being True.
    fields = [
        {"id": "parallel_id", "type": "text", "text": "Parallel ID", "help":parallel_id_help,
            "value": "web1"},
        {"id": "data_path", "type": "text", "text": "Root path to the of check data",
            "value": EXAMPLEDATADIR},
        {"id": "project", "type": "select", "text": "Project", 
            "value": "CORDEX", "allowed_values": ["CORDEX"] },
        {"id": "select", "type": "text", "text": "QC SELECT", "value": "", "help": qc_select_help},
        {"id": "lock", "type": "text", "text": "QC LOCK", "value": "", "help": qc_lock_help},
        {"id": "replica", "type": "checkbox", "text": "Replica", "value": ""},
        {"id": "latest", "type": "checkbox", "text": "Latest", "value": "", "checked": "checked"},
        {"id": "publish_metadata", "type": "checkbox", "text": "Publish meta-data",  "value": "",
            "checked": "checked"},
        {"id": "publish_quality", "type": "checkbox", "text": "Publish quality-data", 
            "value": "", "checked": "checked"},
        {"id": "clean", "type": "checkbox", "text": "Clean afterwards", 
            "value": "", "help": "Removes the work data after the steps have finished"},
        ]
    html_fields = get_html_fields(fields)

    if "submit" in request.POST:
        DATA = request.POST

        wps = get_wps(wps_url(request))
        workflow_description = _create_qc_workflow_v2(DATA, user_id, token, wps)
        #workflow_description = _create_qc_workflow(DATA, user_id, token, wps)

        identifier = 'org.malleefowl.restflow.run'
        inputs = [("workflow_description", str(workflow_description) )]
        outputs = [("output",True)]

        execution = wps.execute(identifier, inputs=inputs, output=outputs)

        add_job(
            request = request,
            user_id = authenticated_userid(request),
            identifier = identifier,
            wps_url = wps.url,
            execution = execution,
            notes = "test",
            tags = "test")

        return HTTPFound(location=request.route_url('jobs'))
    
    return {
            "title": title,
            "html_fields" : html_fields,
            }

def get_parallel_ids(user_id): 
    #If the file path is invalid an empty list is returned.
    path = os.path.join(QCDIR, user_id)
    history_fn = os.path.join(path, "parallel_id.history")
    history = []
    if os.path.isfile(history_fn):
        with open(history_fn, "r") as hist:
            lines = hist.readlines()
            for line in lines:
                history.append(line.rstrip("\n"))  
    existing_history = [x for x in history if os.path.isdir(os.path.join(path, x))] 
    return existing_history

def get_html_fields(fields):
    """
    Converts a fields table with mandatory keywords type, text, id and partially optional 
    keywords value, allowed_values, checked and help into html input lines.

    The tal in the templates has become too complicated therefore the python code handles
    most of the conditions.
    """
    html_fields = []
    for field in fields:
        html_field = {}
        for key in ["help","text","id"]:
            if key in field:
                html_field[key] = field[key]
        if field["type"] == "text":
            html_field["input_html"] = ("<input name=\"" + field["id"] + "\" value=\"" + 
                                        field["value"] + "\" id=\"" + field["id"] + 
                                        "\"type=\"text\">\n")

        if field["type"] == "select":
            html_field["input_html"] = ("<select name=\"" + field["id"] + "\" value=\"" + 
                                        field["value"] + "\">\n")
            for option in field["allowed_values"]:
                html_field["input_html"] += "<option>"+option+"</option>\n"
            html_field["input_html"] += "</select>\n"

        if field["type"] == "checkbox":
            html_field["input_html"] = ("<input name=\"" + field["id"] + "\" value=\"" + 
                                        field["value"] + "\" id=\"" + field["id"] + 
                                        "\"type=\"checkbox\"")
            if "checked" in field:
                html_field["input_html"] += " checked=\"checked\""
            html_field["input_html"] += ">\n"
        html_fields.append(html_field)
    return html_fields
        
####def _create_qc_workflow(DATA, user_id, token, wps):
####    #substitute the @ to avoid complications. 
####    user_id = user_id.replace("@","(at)")
####    token = token
####    parallel_id = DATA["parallel_id"]
####    data_path = DATA["data_path"]
####    project =  DATA["project"]
####    #ensure lock and select are valid values.
####    select = DATA["select"]
####    if select == '<colander.null>' or select == None:
####        select =  ""
####    lock = DATA["lock"]
####    if lock == '<colander.null>' or lock == None:
####        lock =  ""
####    #html checkboxes are true if and only if they are in the POST (DATA variable)
####    replica = "replica" in DATA
####    latest = "latest" in DATA
####    publish_metadata = "publish_metadata" in DATA
####    publish_quality = "publish_quality" in DATA
####    clean = "clean" in DATA
####
####    #Generate the long input lines here to make the yaml_document section easier to read 
####    parallel_id_user_token = ('"parallel_id=' + parallel_id + '", "username=' + user_id + 
####                           '", "token=' + token + '"')
####    #init
####    qc_init_input = '[' + parallel_id_user_token + ', "data_path=' + data_path + '"]'
####    #check
####    qc_check_input = ('[' + parallel_id_user_token + ', "project=' + project)
####    if select != "":
####        qc_check_input += '", "select=' + select 
####    if lock != "":
####        qc_check_input += '", "lock=' + lock 
####    qc_check_input += '"]'
####    #eval
####    qc_eval_input = ('[' + parallel_id_user_token + ', "replica=' + str(replica).lower() +
####                     '", "latest=' + str(latest).lower() + '"]')
####    wps_address = wps.url
####    #publish meta
####    publish_meta_input = '[' + parallel_id_user_token + ']'
####    #publish quality 
####    publish_quality_input = '[' + parallel_id_user_token + ']'
####    #clean
####    clean_input = ('["parallel_ids=' + parallel_id + '", "username=' + user_id +
####                   '", "token=' + token + '"]')
####
####    #document
####    yaml_document = [
####        "---",
####        "",
####        "imports:",
####        "- classpath:/common/directors.yaml",
####        "- classpath:/common/groovy/actors.yaml",
####        "components:",
####        "- id: QCProcesses",
####        "  type: Workflow",
####        "  properties:",
####        "    director: !ref MTDataDrivenDirector",
####        "    nodes:",
####        "    - !ref InputGenerator",
####        "    - !ref QC_Init",
####        "    - !ref QC_Check",
####        "    - !ref QC_Eval",]
####    if publish_metadata:
####        yaml_document.append("    - !ref QC_Publish_Meta")
####    if publish_quality:
####        yaml_document.append("    - !ref QC_Publish_Quality")
####    if clean:
####        yaml_document+= [
####        "    - !ref QC_Clean",
####        "    - !ref QC_Merge_For_Clean",
####        ]
####    yaml_document += [
####        "    - !ref WriteResult",
####        "    - !ref WriteStatus",
####        "",
####        "- id: InputGenerator",
####        "  type: GroovyActorNode",
####        "  properties:",
####        "    actor.step: | ",
####        '      run = "run"',]
####
####    if not publish_metadata:
####        yaml_document.append('      finished_publish_meta = "run"')
####    if not publish_quality:
####        yaml_document.append('      finished_publish_quality = "run"')
####    yaml_document += [
####        "    outflows:",
####        "      run: /variable/init_run/",]
####    if not publish_metadata:
####        yaml_document.append("      finished_publish_meta: /variable/publish_meta_finished/")
####    if not publish_quality:
####        yaml_document.append("      finished_publish_quality: /variable/publish_quality_finished/")
####    yaml_document += [
####        "",
####        "- id: WpsExecute",
####        "  type: GroovyActor",
####        "  properties:",
####        "    step: |",
####        "      tempFile = File.createTempFile('wps-result-', '.json', new File('.'))",
####        "      outfile = tempFile.absolutePath",
####        "      cmd = ['wpsclient', 'execute', ",
####        "                    '-s', service,",
####        "                    '-i', identifier,",
####        "                    '-o', outfile]",
####        "      if (verbose) {",
####        "          cmd.add('-v')",
####        "      }",
####        "      for (item in sources) {",
####        "          cmd.add('--input')",
####        "          cmd.add('file_identifier=' + item.value)",
####        "      }",
####        "      for (item in input) {",
####        "          cmd.add('--input')",
####        "          cmd.add('' + item.value)",
####        "      }",
####        "      for (item in output) {",
####        "          cmd.add('--output')",
####        "          cmd.add('' + item.value)",
####        "      }",
####        "     ",
####        "      proc = cmd.execute()",
####        "      proc.waitFor()",
####        "      result = identifier + ' ... failed'",
####        "      status = result",
####        "      import org.yaml.snakeyaml.Yaml",
####        "      resultFile = new File(outfile)",
####        "      if (resultFile.exists()) {",
####        "         yaml = new Yaml()",
####        "         wpsResult = yaml.load(new FileInputStream(resultFile))",
####        "     ",
####        "         for (item in wpsResult) {",
####        "            result = item.reference",
####        "            status = identifier + ' ... done'",
####        "         }",
####        "      }",
####        "      finished = run",
####        "    inputs:",
####        "      run:",
####        "      identifier: ",
####        "      service:",
####        "      input:",
####        "        type: Collection",
####        "        optional: true",
####        "        nullable: true",
####        "      output:",
####        "        type: Collection",
####        "        optional: true",
####        "        nullable: true",
####        "      sources:",
####        "        type: Collection",
####        "        optional: true",
####        "        nullable: true",
####        "      verbose:",
####        "        type: Bool",
####        "    outputs:",
####        #"      result:",
####        #"      status:",
####        "      finished:",
####        "",
####        "- id: Three_To_One",
####        "  type: GroovyActor",
####        "  properties:",
####        "    step: |",
####        "      finished = run",
####        "    inputs:",
####        "      run:",
####        "      run2:",
####        "      run3:",
####        "    outputs:",
####        "      finished:",
####        "",
####        "- id: QC_Init",
####        "  type: Node",
####        "  properties:",
####        "    actor: !ref WpsExecute",
####        "    constants:",
####        "      service: " + wps_address,
####        "      identifier: QC_Init_User",
####        "      input: " + qc_init_input, 
####        "      output: [('output',True)]",
####        "    inflows:",
####        "      run: /variable/init_run/",
####        "    outflows:",
####        "      finished: /variable/init_finished/",
####        "",
####        "- id: QC_Check",
####        "  type: Node",
####        "  properties:",
####        "    actor: !ref WpsExecute",
####        "    constants:",
####        "      service: " + wps_address,
####        "      identifier: QC_Check_User",
####        "      input: " + qc_check_input, 
####        "      output: []",
####        "    inflows:",
####        "      run : /variable/init_finished/",
####        "    outflows:",
####        "      finished: /variable/check_finished/",
####        "",
####        "- id: QC_Eval",
####        "  type: Node",
####        "  properties:",
####        "    actor: !ref WpsExecute",
####        "    constants:",
####        "      service: " + wps_address,
####        "      identifier: QC_Eval_User",
####        "      input: " + qc_eval_input,
####        "      output: []",
####        "    inflows:",
####        "      run : /variable/check_finished/",
####        "    outflows:",
####        "      finished: /variable/eval_finished/",
####       ]
####    if publish_metadata:
####        yaml_document += [
####        "",
####        "- id: QC_Publish_Meta",
####        "  type: Node",
####        "  properties:",
####        "    actor: !ref WpsExecute",
####        "    constants:",
####        "      service: " + wps_address,
####        "      identifier: QC_MetaPublisher_User", 
####        "      input: " + publish_meta_input,
####        "      output: []",
####        "    inflows:",
####        "      run : /variable/eval_finished/",
####        "    outflows:",
####        "      finished: /variable/publish_meta_finished/",
####        ]
####
####    if publish_quality:
####        yaml_document += [
####        "",
####        "- id: QC_Publish_Quality",
####        "  type: Node",
####        "  properties:",
####        "    actor: !ref WpsExecute",
####        "    constants:",
####        "      service: " + wps_address,
####        "      identifier: QC_QualityPublisher_User", 
####        "      input: " + publish_quality_input,
####        "      output: []",
####        "    inflows:",
####        "      run : /variable/eval_finished/",
####        "    outflows:",
####        "      finished: /variable/publish_quality_finished/",
####        ]
####    if clean:
####        yaml_document += [
####        "- id: QC_Merge_For_Clean",
####        "  type: Node",
####        "  properties:",
####        "    actor: !ref Three_To_One",
####        "    inflows:",
####        "      run : /variable/publish_quality_finished/",
####        "      run2: /variable/publish_meta_finished/",
####        "      run3: /variable/eval_finished/",
####        "    outflows:",
####        "      finished: /variable/clean_start/",
####        "",
####        "- id: QC_Clean",
####        "  type: Node",
####        "  properties:",
####        "    actor: !ref WpsExecute",
####        "    constants:",
####        "      service: " + wps_address,
####        "      identifier: QC_RemoveData_User", 
####        "      input: " + clean_input,
####        "      output: []",
####        "    inflows:",
####        "      run : /variable/clean_start/",
####        "    outflows:",
####        "      finished: /variable/clean_finished/",
####        ]
####    yaml_document += [
####        "",
####        #add the org.mallefowl.restflow.run required parts
####        "- id: FileWriter",
####        "  type: GroovyActor",
####        "  properties:",
####        "    step: |",
####        "      f = new File(filename)",
####        "      f.write(message)",
####        "    inputs:",
####        "      filename:",
####        "        type: String",
####        "      message:",
####        "        type: String",
####        "",
####        "- id: WriteResult",
####        "  type: Node",
####        "  properties:",
####        "    actor: !ref FileWriter",
####        "    constants:",
####        "      filename: restflow_output.txt",
####        "    inflows:",
####        "      message: /variable/eval_finished/",
####        "",
####        "- id: WriteStatus",
####        "  type: Node",
####        "  properties:",
####        "    actor: !ref FileWriter",
####        "    constants:",
####        "      filename: restflow_status.txt",
####        "    inflows:",
####        "      message: /variable/eval_finished/",
####        ]
####    document = "\n".join(yaml_document)+"\n"
####    return document

def _create_qc_workflow_v2(DATA, user_id, token, wps):
    #substitute the @ to avoid complications. 
    user_id = user_id.replace("@","(at)")
    token = token
    parallel_id = DATA["parallel_id"]
    data_path = DATA["data_path"]
    project =  DATA["project"]
    #ensure lock and select are valid values.
    select = DATA["select"]
    if select == '<colander.null>' or select == None:
        select =  ""
    lock = DATA["lock"]
    if lock == '<colander.null>' or lock == None:
        lock =  ""
    #html checkboxes are true if and only if they are in the POST (DATA variable)
    replica = "replica" in DATA
    latest = "latest" in DATA
    publish_metadata = "publish_metadata" in DATA
    publish_quality = "publish_quality" in DATA
    clean = "clean" in DATA

    yaml_document = [
        '---',
        '',
        'imports:',
        '- classpath:/common/directors.yaml',
        '- classpath:/common/groovy/actors.yaml',
        'components:',
        '- id: QCProcesses',
        '  type: Workflow',
        '  properties:',
        '    director: !ref MTDataDrivenDirector',
        '    nodes:',
        '    - !ref InputGenerator',
        '    - !ref MergeInputInit',
        '    - !ref MergeInputCheck',
        '    - !ref MergeInputEval',
        '    - !ref MergeInputPublishMeta',
        '    - !ref MergeInputPublishQuality',
        '    - !ref ActivateClean',
        '    - !ref QC_Init',
        '    - !ref QC_Check',
        '    - !ref QC_Eval',
        '    - !ref QC_Publish_Meta',
        '    - !ref QC_Publish_Quality',
        '    - !ref QC_Clean',
        '    - !ref Merge_Results',
        '    - !ref WriteResult',
        '    - !ref WriteStatus',
        '',
        '',
        '- id: WpsExecute',
        '  type: GroovyActor',
        '  properties:',
        '    step: |',
        '      import org.yaml.snakeyaml.Yaml',
        '      if (enable) {',
        '        tempFile = File.createTempFile("wps-result-", ".json", new File("."))',
        '        outfile = tempFile.absolutePath',
        '        cmd = ["wpsclient", "execute", ',
        '                      "-s", service,',
        '                      "-i", identifier,',
        '                      "-o", outfile]',
        '        if (verbose) {',
        '          cmd.add("-v")',
        '        }',
        '        for (item in sources) {',
        '          cmd.add("--input")',
        '          cmd.add("file_identifier=" + item.value)',
        '        }',
        '        for (item in input) {',
        '          cmd.add("--input")',
        '          cmd.add("" + item.value)',
        '        }',
        '        for (item in output) {',
        '          cmd.add("--output")',
        '          cmd.add("" + item.value)',
        '        }',
        '',
        '        proc = cmd.execute()',
        '        proc.waitFor()',
        '        result = identifier + " ... failed"',
        '        status = result',
        '        resultFile = new File(outfile)',
        '        if (resultFile.exists()) {',
        '           yaml = new Yaml()',
        '           wpsResult = yaml.load(new FileInputStream(resultFile))',
        '           result = "Results for process " + identifier + ":\\n"',
        '',
        '           for (item in wpsResult) {',
        '             result += item.reference + "\\n"',
        '             status = identifier + " ... done"',
        '           }',
        '        }',
        '      }',
        '      else {',
        '        result = "Process " + identifier + " was disabled"',
        '      }',
        '      println(identifier + enable)',
        '      finished = identifier',
        '    inputs:',
        '      service:',
        '      run:',
        '      enable:',
        '      identifier:',
        '      input:',
        '        type: Collection',
        '        optional: true',
        '        nullable: true',
        '      output:',
        '        type: Collection',
        '        optional: true',
        '        nullable: true',
        '      sources:',
        '        type: Collection',
        '        optional: true',
        '        nullable: true',
        '      verbose:',
        '        type: Bool',
        '    outputs:',
        '      result:',
        '      finished:',
        '',
        '- id: InputGenerator',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: |',
        '        username = "' + user_id + '"',
        '        parallel_id = "' + parallel_id + '"',
        '        token = "' + token + '"',
        '        service = "' + wps.url + '"',
        '        data_path = "' + data_path + '"',
        '        select = "' + select + '"',
        '        lock = "' + lock + '"',
        '        project = "' + project + '"',
        '        replica = ' + str(replica).lower(),
        '        latest = ' + str(latest).lower(),
        '        init_enable = true',
        '        init_identifier = "QC_Init"',
        '        init_output = ["process_log", "all_okay"]',#[["all_okay",true]]',
        '        init_run = "run"',
        '        check_enable = true',
        '        check_identifier = "QC_Check"',
        '        check_output = ["qc_call", "qc_call_exit_code", "qc_svn_version", "error_messages"]',
        '        eval_enable = true',
        '        eval_identifier = "QC_Evaluate"',
       ('        eval_output = ["found_tags", "fail_count", "pass_count", "omit_count", "fixed_count"' +
                               ', "has_issues", "process_log", "to_publish_qc_files",' + 
                               '"to_publish_metadata_files", "found_pids"]'),
        '        publish_meta_enable = ' + str(publish_metadata).lower(),
        '        publish_meta_identifier = "QC_MetaPublisher"',
        '        publish_meta_output = ["process_log"]',
        '        publish_quality_enable = ' + str(publish_quality).lower(),
        '        publish_quality_identifier = "QC_QualityPublisher"',
        '        publish_quality_output = ["process_log"]',
        '        clean_enable = ' + str(clean).lower(),
        '        clean_identifier = "QC_RemoveData"',
        '        clean_output = []',
        '    outflows:',
        '        username: /variable/username/',
        '        parallel_id: /variable/parallel_id/',
        '        token: /variable/token/',
        '        service: /variable/service/',
        '        data_path: /variable/data_path/',
        '        select: /variable/select/',
        '        lock: /variable/lock/',
        '        project: /variable/project/',
        '        replica: /variable/replica/',
        '        latest: /variable/latest/',
        '        init_enable: /variable/init_enable/',
        '        init_identifier: /variable/init_id/',
        '        init_output: /variable/init_output/',
        '        init_run: /variable/init_run/',
        '        check_enable: /variable/check_enable/',
        '        check_identifier: /variable/check_id/',
        '        check_output: /variable/check_output/',
        '        eval_enable: /variable/eval_enable/',
        '        eval_identifier: /variable/eval_id/',
        '        eval_output: /variable/eval_output/',
        '        publish_meta_enable: /variable/publish_meta_enable/',
        '        publish_meta_identifier: /variable/publish_meta_id/',
        '        publish_meta_output: /variable/publish_meta_output/',
        '        publish_quality_enable: /variable/publish_quality_enable/',
        '        publish_quality_identifier: /variable/publish_quality_id/',
        '        publish_quality_output: /variable/publish_quality_output/',
        '        clean_enable: /variable/clean_enable/',
        '        clean_identifier: /variable/clean_id/',
        '        clean_output: /variable/clean_output/',
        '',
        '',
        '- id: MergeInputInit',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: | ',
        '      inputs = ["parallel_id=" + parallel_id, "username=" + username, "token=" + token] ',
        '      inputs.add("datapath=" + data_path)',
        '    inflows:',
        '      parallel_id: /variable/parallel_id/',
        '      username: /variable/username/',
        '      token: /variable/token/',
        '      data_path: /variable/data_path/',
        '',
        '    outflows:',
        '      inputs: /variable/init_input/',
        '',
        '- id: MergeInputCheck',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: | ',
        '      inputs = ["parallel_id=" + parallel_id, "username=" + username, "token=" + token] ',
        '      inputs.add("project=" + project)',
        '      if (select != "") {',
        '        inputs.add("select=" + select)',
        '      }',
        '      if (lock != "") {',
        '        inputs.add("lock=" + lock)',
        '      }',
        '    inflows:',
        '      parallel_id: /variable/parallel_id/',
        '      username: /variable/username/',
        '      token: /variable/token/',
        '      project: /variable/project/ ',
        '      select: /variable/select/',
        '      lock: /variable/lock/',
        '    outflows:',
        '      inputs: /variable/check_input/',
        '',
        '- id: MergeInputEval',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: | ',
        '      inputs = ["parallel_id=" + parallel_id, "username=" + username, "token=" + token] ',
        '      inputs.add("latest=" + latest)',
        '      inputs.add("replica=" + replica)',
        '    inflows:',
        '      parallel_id: /variable/parallel_id/',
        '      username: /variable/username/',
        '      token: /variable/token/',
        '      latest: /variable/latest/ ',
        '      replica: /variable/replica/ ',
        '    outflows:',
        '      inputs: /variable/eval_input/',
        '',
        '- id: MergeInputPublishMeta',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: | ',
        '      inputs = ["parallel_id=" + parallel_id, "username=" + username, "token=" + token] ',
        '    inflows:',
        '      parallel_id: /variable/parallel_id/',
        '      username: /variable/username/',
        '      token: /variable/token/',
        '    outflows:',
        '      inputs: /variable/publish_meta_input/',
        '',
        '- id: MergeInputPublishQuality',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: | ',
        '      inputs = ["parallel_id=" + parallel_id, "username=" + username, "token=" + token] ',
        '    inflows:',
        '      parallel_id: /variable/parallel_id/',
        '      username: /variable/username/',
        '      token: /variable/token/',
        '    outflows:',
        '      inputs: /variable/publish_quality_input/',
        '',
        '- id: ActivateClean',
        '  type: GroovyActorNode',
        '  properties: ',
        '    actor.step: |',
        '      run = "run"',
        '      inputs = ["parallel_ids=" + parallel_id, "username=" + username, "token=" + token] ',
        '    inflows:',
        '      c1: /variable/publish_quality_finished/',
        '      c2: /variable/publish_meta_finished/',
        '      parallel_id: /variable/parallel_id/',
        '      username: /variable/username/',
        '      token: /variable/token/',
        '    outflows:',
        '      run: /variable/clean_run/',
        '      inputs: /variable/clean_input/',
        '',
        '- id: QC_Init',
        '  type: Node',
        '  properties:',
        '    actor: !ref WpsExecute',
        '    inflows: ',
        '      service: /variable/service/',
        '      run: /variable/init_run/',
        '      enable: /variable/init_enable/',
        '      identifier: /variable/init_id/',
        '      input: /variable/init_input/',
        '      output: /variable/init_output/',
        '    outflows:',
        '      finished: /variable/init_finished/',
        '      result: /variable/init_result/',
        '',
        '- id: QC_Check',
        '  type: Node',
        '  properties:',
        '    actor: !ref WpsExecute',
        '    inflows: ',
        '      service: /variable/service/',
        '      run: /variable/init_finished/',
        '      enable: /variable/check_enable/',
        '      identifier: /variable/check_id/',
        '      input: /variable/check_input/',
        '      output: /variable/check_output/',
        '    outflows:',
        '      finished: /variable/check_finished/',
        '      result: /variable/check_result/',
        '',
        '',
        '- id: QC_Eval',
        '  type: Node',
        '  properties:',
        '    actor: !ref WpsExecute',
        '    inflows: ',
        '      service: /variable/service/',
        '      run: /variable/check_finished/',
        '      enable: /variable/eval_enable/',
        '      identifier: /variable/eval_id/',
        '      input: /variable/eval_input/',
        '      output: /variable/eval_output/',
        '    outflows:',
        '      finished: /variable/eval_finished/',
        '      result: /variable/eval_result/',
        '',
        '- id: QC_Publish_Meta',
        '  type: Node',
        '  properties:',
        '    actor: !ref WpsExecute',
        '    inflows: ',
        '      service: /variable/service/',
        '      run: /variable/eval_finished/',
        '      enable: /variable/publish_meta_enable/',
        '      identifier: /variable/publish_meta_id/',
        '      input: /variable/publish_meta_input/',
        '      output: /variable/publish_meta_output/',
        '    outflows:',
        '      finished: /variable/publish_meta_finished/',
        '      result: /variable/publish_meta_result/',
        '',
        '- id: QC_Publish_Quality',
        '  type: Node',
        '  properties:',
        '    actor: !ref WpsExecute',
        '    inflows: ',
        '      service: /variable/service/',
        '      run: /variable/eval_finished/',
        '      enable: /variable/publish_quality_enable/',
        '      identifier: /variable/publish_quality_id/',
        '      input: /variable/publish_quality_input/',
        '      output: /variable/publish_quality_output/',
        '    outflows:',
        '      finished: /variable/publish_quality_finished/',
        '      result: /variable/publish_quality_result/',
        '',
        '- id: QC_Clean',
        '  type: Node',
        '  properties:',
        '    actor: !ref WpsExecute',
        '    inflows: ',
        '      service: /variable/service/',
        '      run: /variable/clean_run/',
        '      enable: /variable/clean_enable/',
        '      identifier: /variable/clean_id/',
        '      input: /variable/clean_input/',
        '      output: /variable/clean_output/',
        '    outflows:',
        '      finished: /variable/clean_finished/',
        '      result: /variable/clean_result/',
        '',
        '- id: Merge_Results',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: |',
        '      output = ""',
        '      output += init_result + "\\n"',
        '      output += check_result + "\\n"',
        '      output += eval_result + "\\n"',
        '      output += publish_meta_result + "\\n"',
        '      output += publish_quality_result + "\\n"',
        '      output += clean_result + "\\n"',
        '    inflows:',
        '      init_result: /variable/init_result/',
        '      check_result: /variable/check_result/',
        '      eval_result: /variable/eval_result/',
        '      publish_meta_result: /variable/publish_meta_result/',
        '      publish_quality_result: /variable/publish_quality_result/',
        '      clean_result: /variable/clean_result/',
        '    outflows:',
        '      output: /variable/merge_result/',
        '',
        '- id: FileWriter',
        '  type: GroovyActor',
        '  properties:',
        '    step: |',
        '      f = new File(filename)',
        '      f.write(message)',
        '    inputs:',
        '      filename:',
        '        type: String',
        '      message:',
        '        type: String',
        '',
        '- id: WriteResult',
        '  type: Node',
        '  properties:',
        '    actor: !ref FileWriter',
        '    constants:',
        '      filename: restflow_output.txt',
        '    inflows:',
        '      message: /variable/merge_result/',
        '',
        '- id: WriteStatus',
        '  type: Node',
        '  properties:',
        '    actor: !ref FileWriter',
        '    constants:',
        '      filename: restflow_status.txt',
        '    inflows:',
        '      message: /variable/clean_finished/',
        ]
    document = "\n".join(yaml_document)+"\n"
    return document

@view_config(route_name='qc_wizard_yaml',
             renderer='templates/qc_wizard.pt',
             layout='default',
             permission='edit',
             )
def qc_wizard_yaml(request):
    title = "Quality Control Wizard"
    user_id = authenticated_userid(request)
    token = user_token(request, user_id)
    
    parallel_id_help = ("An identifier used to avoid processes running on the same directory." + 
                        " Using an existing one will remove all data inside its work directory.")
    parallel_ids = get_parallel_ids(user_id)
    if parallel_ids == []:
        parallel_id_help += " There are currently no existing Parallel IDs."
    else:
        parallel_id_help += " The existing Parallel IDs are:<br>" +", ".join(parallel_ids)
    yamllogs_help = "The comma separated list of logfile locations"
    oldprefix_help = "The data path in the provided logfiles"
    newprefix_help = "The data path on the machine"

    #a field in fields must contain text, id and value. The entry help is optional.
    #allowed_values can be used if a limited number of possibile values should be available.
    #In that case value will be used as default if it is in allowed_values.
    #For type "checkbox" the existence of the "checked" key will lead to the checkbox being True.
    fields = [
        {"id": "parallel_id", "type": "text", "text": "Parallel ID", "help":parallel_id_help,
            "value": "checkdone"},
        {"id": "yamllogs", "type": "text", "text": "YAML logs", "help": yamllogs_help, "value": ""},
        {"id": "prefix_old", "type": "text", "text": "Old prefix", "help": oldprefix_help, "value": ""},
        {"id": "prefix_new", "type": "text", "text": "New prefix", "help": newprefix_help, "value": ""},
        {"id": "project", "type": "select", "text": "Project", 
            "value": "CORDEX", "allowed_values": ["CORDEX"] },
        {"id": "replica", "type": "checkbox", "text": "Replica", "value": ""},
        {"id": "latest", "type": "checkbox", "text": "Latest", "value": "", "checked": "checked"},
        {"id": "publish_metadata", "type": "checkbox", "text": "Publish meta-data",  "value": "",
            "checked": "checked"},
        {"id": "publish_quality", "type": "checkbox", "text": "Publish quality-data", 
            "value": "", "checked": "checked"},
        {"id": "clean", "type": "checkbox", "text": "Clean afterwards", 
            "value": "", "help": "Removes the work data after the steps have finished"},
        ]
    html_fields = get_html_fields(fields)

    if "submit" in request.POST:
        DATA = request.POST

        wps = get_wps(wps_url(request))
        workflow_description = _create_qc_workflow_yaml(DATA, user_id, token, wps)

        identifier = 'org.malleefowl.restflow.run'
        inputs = [("workflow_description", str(workflow_description) )]
        outputs = [("output",True)]

        execution = wps.execute(identifier, inputs=inputs, output=outputs)

        add_job(
            request = request,
            user_id = authenticated_userid(request),
            identifier = identifier,
            wps_url = wps.url,
            execution = execution,
            notes = "test",
            tags = "test")

        return HTTPFound(location=request.route_url('jobs'))
    
    return {"title": title, "html_fields" : html_fields}

def _create_qc_workflow_yaml(DATA, user_id, token, wps):
    #substitute the @ to avoid complications. 
    user_id = user_id.replace("@","(at)")
    token = token
    yamllogs = [str(x.strip()) for x in DATA["yamllogs"].split(',')]
    prefix_old = DATA["prefix_old"]
    prefix_new = DATA["prefix_new"]
    parallel_id = DATA["parallel_id"]
    #html checkboxes are true if and only if they are in the POST (DATA variable)
    replica = "replica" in DATA
    latest = "latest" in DATA
    publish_metadata = "publish_metadata" in DATA
    publish_quality = "publish_quality" in DATA
    clean = "clean" in DATA

    yaml_document = [
        '---',
        '',
        'imports:',
        '- classpath:/common/directors.yaml',
        '- classpath:/common/groovy/actors.yaml',
        'components:',
        '- id: QCProcesses',
        '  type: Workflow',
        '  properties:',
        '    director: !ref MTDataDrivenDirector',
        '    nodes:',
        '    - !ref InputGenerator',
        '    - !ref MergeInputInit',
        '    - !ref MergeInputEval',
        '    - !ref MergeInputPublishMeta',
        '    - !ref MergeInputPublishQuality',
        '    - !ref ActivateClean',
        '    - !ref QC_Init',
        '    - !ref QC_Eval',
        '    - !ref QC_Publish_Meta',
        '    - !ref QC_Publish_Quality',
        '    - !ref QC_Clean',
        '    - !ref Merge_Results',
        '    - !ref WriteResult',
        '    - !ref WriteStatus',
        '',
        '- id: WpsExecute',
        '  type: GroovyActor',
        '  properties:',
        '    step: |',
        '      import org.yaml.snakeyaml.Yaml',
        '      if (enable) {',
        '        tempFile = File.createTempFile("wps-result-", ".json", new File("."))',
        '        outfile = tempFile.absolutePath',
        '        cmd = ["wpsclient", "execute", ',
        '                      "-s", service,',
        '                      "-i", identifier,',
        '                      "-o", outfile]',
        '        if (verbose) {',
        '          cmd.add("-v")',
        '        }',
        '        for (item in sources) {',
        '          cmd.add("--input")',
        '          cmd.add("file_identifier=" + item.value)',
        '        }',
        '        for (item in input) {',
        '          cmd.add("--input")',
        '          cmd.add("" + item.value)',
        '        }',
        '        for (item in output) {',
        '          cmd.add("--output")',
        '          cmd.add("" + item.value)',
        '        }',
        '',
        '        proc = cmd.execute()',
        '        proc.waitFor()',
        '        result = identifier + " ... failed"',
        '        status = result',
        '        resultFile = new File(outfile)',
        '        if (resultFile.exists()) {',
        '           yaml = new Yaml()',
        '           wpsResult = yaml.load(new FileInputStream(resultFile))',
        '           result = "Results for process " + identifier + ":\\n"',
        '',
        '           for (item in wpsResult) {',
        '             result += item.reference + "\\n"',
        '             status = identifier + " ... done"',
        '           }',
        '        }',
        '      }',
        '      else {',
        '        result = "Process " + identifier + " was disabled"',
        '      }',
        '      println(identifier + enable)',
        '      finished = identifier',
        '    inputs:',
        '      service:',
        '      run:',
        '      enable:',
        '      identifier:',
        '      input:',
        '        type: Collection',
        '        optional: true',
        '        nullable: true',
        '      output:',
        '        type: Collection',
        '        optional: true',
        '        nullable: true',
        '      sources:',
        '        type: Collection',
        '        optional: true',
        '        nullable: true',
        '      verbose:',
        '        type: Bool',
        '    outputs:',
        '      result:',
        '      finished:',
        '',
        '- id: InputGenerator',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: |',
        '        username = "' + user_id + '"',
        '        parallel_id = "' + parallel_id + '"',
        '        token = "' + token + '"',
        '        service = "' + wps.url + '"',
        '        replica = ' + str(replica).lower(),
        '        latest = ' + str(latest).lower(),
        '        yamllogs = ' + str(yamllogs) + '',
        '        prefix_old = "' + prefix_old + '"',
        '        prefix_new = "' + prefix_new + '"',
        '        init_enable = true',
        '        init_identifier = "QC_Init_With_Yamllogs"',
        '        init_output = ["process_log", "all_okay"]',
        '        init_run = "run"',
        '        eval_enable = true',
        '        eval_identifier = "QC_Evaluate"',
       ('        eval_output = ["found_tags", "fail_count", "pass_count", "omit_count", "fixed_count"' +
                               ', "has_issues", "process_log", "to_publish_qc_files",' + 
                               '"to_publish_metadata_files", "found_pids"]'),
        '        publish_meta_enable = ' + str(publish_metadata).lower(),
        '        publish_meta_identifier = "QC_MetaPublisher"',
        '        publish_meta_output = ["process_log"]',
        '        publish_quality_enable = ' + str(publish_quality).lower(),
        '        publish_quality_identifier = "QC_QualityPublisher"',
        '        publish_quality_output = ["process_log"]',
        '        clean_enable = ' + str(clean).lower(),
        '        clean_identifier = "QC_RemoveData"',
        '        clean_output = []',
        '    outflows:',
        '        username: /variable/username/',
        '        parallel_id: /variable/parallel_id/',
        '        token: /variable/token/',
        '        service: /variable/service/',
        '        replica: /variable/replica/',
        '        latest: /variable/latest/',
        '        yamllogs: /variable/yamllogs/',
        '        prefix_old: /variable/prefix_old/',
        '        prefix_new: /variable/prefix_new/',
        '        init_enable: /variable/init_enable/',
        '        init_identifier: /variable/init_id/',
        '        init_output: /variable/init_output/',
        '        init_run: /variable/init_run/',
        '        eval_enable: /variable/eval_enable/',
        '        eval_identifier: /variable/eval_id/',
        '        eval_output: /variable/eval_output/',
        '        publish_meta_enable: /variable/publish_meta_enable/',
        '        publish_meta_identifier: /variable/publish_meta_id/',
        '        publish_meta_output: /variable/publish_meta_output/',
        '        publish_quality_enable: /variable/publish_quality_enable/',
        '        publish_quality_identifier: /variable/publish_quality_id/',
        '        publish_quality_output: /variable/publish_quality_output/',
        '        clean_enable: /variable/clean_enable/',
        '        clean_identifier: /variable/clean_id/',
        '        clean_output: /variable/clean_output/',
        '',
        '- id: MergeInputInit',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: | ',
        '      inputs = ["parallel_id=" + parallel_id, "username=" + username, "token=" + token] ',
        #'      yaml_logs = "yamllogs="',
        '      for (item in yamllogs){',
        '          inputs.add("yamllogs=" + item)',       
        '      }',
        '      inputs.add("prefix_old=" + prefix_old)', 
        '      inputs.add("prefix_new=" + prefix_new)',
        '    inflows:',
        '      parallel_id: /variable/parallel_id/',
        '      username: /variable/username/',
        '      token: /variable/token/',
        '      yamllogs: /variable/yamllogs/',
        '      prefix_old: /variable/prefix_old/',
        '      prefix_new: /variable/prefix_new/',
        '    outflows:',
        '      inputs: /variable/init_input/',
        '',
        '- id: MergeInputEval',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: | ',
        '      inputs = ["parallel_id=" + parallel_id, "username=" + username, "token=" + token] ',
        '      inputs.add("latest=" + latest)',
        '      inputs.add("replica=" + replica)',
        '    inflows:',
        '      parallel_id: /variable/parallel_id/',
        '      username: /variable/username/',
        '      token: /variable/token/',
        '      latest: /variable/latest/ ',
        '      replica: /variable/replica/ ',
        '    outflows:',
        '      inputs: /variable/eval_input/',
        '',
        '- id: MergeInputPublishMeta',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: | ',
        '      inputs = ["parallel_id=" + parallel_id, "username=" + username, "token=" + token] ',
        '    inflows:',
        '      parallel_id: /variable/parallel_id/',
        '      username: /variable/username/',
        '      token: /variable/token/',
        '    outflows:',
        '      inputs: /variable/publish_meta_input/',
        '',
        '- id: MergeInputPublishQuality',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: | ',
        '      inputs = ["parallel_id=" + parallel_id, "username=" + username, "token=" + token] ',
        '    inflows:',
        '      parallel_id: /variable/parallel_id/',
        '      username: /variable/username/',
        '      token: /variable/token/',
        '    outflows:',
        '      inputs: /variable/publish_quality_input/',
        '',
        '- id: ActivateClean',
        '  type: GroovyActorNode',
        '  properties: ',
        '    actor.step: |',
        '      run = "run"',
        '      inputs = ["parallel_ids=" + parallel_id, "username=" + username, "token=" + token] ',
        '    inflows:',
        '      c1: /variable/publish_quality_finished/',
        '      c2: /variable/publish_meta_finished/',
        '      parallel_id: /variable/parallel_id/',
        '      username: /variable/username/',
        '      token: /variable/token/',
        '    outflows:',
        '      run: /variable/clean_run/',
        '      inputs: /variable/clean_input/',
        '',
        '- id: QC_Init',
        '  type: Node',
        '  properties:',
        '    actor: !ref WpsExecute',
        '    inflows: ',
        '      service: /variable/service/',
        '      run: /variable/init_run/',
        '      enable: /variable/init_enable/',
        '      identifier: /variable/init_id/',
        '      input: /variable/init_input/',
        '      output: /variable/init_output/',
        '    outflows:',
        '      finished: /variable/init_finished/',
        '      result: /variable/init_result/',
        '',
        '- id: QC_Eval',
        '  type: Node',
        '  properties:',
        '    actor: !ref WpsExecute',
        '    inflows: ',
        '      service: /variable/service/',
        '      run: /variable/init_finished/',
        '      enable: /variable/eval_enable/',
        '      identifier: /variable/eval_id/',
        '      input: /variable/eval_input/',
        '      output: /variable/eval_output/',
        '    outflows:',
        '      finished: /variable/eval_finished/',
        '      result: /variable/eval_result/',
        '',
        '- id: QC_Publish_Meta',
        '  type: Node',
        '  properties:',
        '    actor: !ref WpsExecute',
        '    inflows: ',
        '      service: /variable/service/',
        '      run: /variable/eval_finished/',
        '      enable: /variable/publish_meta_enable/',
        '      identifier: /variable/publish_meta_id/',
        '      input: /variable/publish_meta_input/',
        '      output: /variable/publish_meta_output/',
        '    outflows:',
        '      finished: /variable/publish_meta_finished/',
        '      result: /variable/publish_meta_result/',
        '',
        '- id: QC_Publish_Quality',
        '  type: Node',
        '  properties:',
        '    actor: !ref WpsExecute',
        '    inflows: ',
        '      service: /variable/service/',
        '      run: /variable/eval_finished/',
        '      enable: /variable/publish_quality_enable/',
        '      identifier: /variable/publish_quality_id/',
        '      input: /variable/publish_quality_input/',
        '      output: /variable/publish_quality_output/',
        '    outflows:',
        '      finished: /variable/publish_quality_finished/',
        '      result: /variable/publish_quality_result/',
        '',
        '- id: QC_Clean',
        '  type: Node',
        '  properties:',
        '    actor: !ref WpsExecute',
        '    inflows: ',
        '      service: /variable/service/',
        '      run: /variable/clean_run/',
        '      enable: /variable/clean_enable/',
        '      identifier: /variable/clean_id/',
        '      input: /variable/clean_input/',
        '      output: /variable/clean_output/',
        '    outflows:',
        '      finished: /variable/clean_finished/',
        '      result: /variable/clean_result/',
        '',
        '- id: Merge_Results',
        '  type: GroovyActorNode',
        '  properties:',
        '    actor.step: |',
        '      output = ""',
        '      output += init_result + "\\n"',
        '      output += eval_result + "\\n"',
        '      output += publish_meta_result + "\\n"',
        '      output += publish_quality_result + "\\n"',
        '      output += clean_result + "\\n"',
        '    inflows:',
        '      init_result: /variable/init_result/',
        '      eval_result: /variable/eval_result/',
        '      publish_meta_result: /variable/publish_meta_result/',
        '      publish_quality_result: /variable/publish_quality_result/',
        '      clean_result: /variable/clean_result/',
        '    outflows:',
        '      output: /variable/merge_result/',
        '',
        '- id: FileWriter',
        '  type: GroovyActor',
        '  properties:',
        '    step: |',
        '      f = new File(filename)',
        '      f.write(message)',
        '    inputs:',
        '      filename:',
        '        type: String',
        '      message:',
        '        type: String',
        '',
        '- id: WriteResult',
        '  type: Node',
        '  properties:',
        '    actor: !ref FileWriter',
        '    constants:',
        '      filename: restflow_output.txt',
        '    inflows:',
        '      message: /variable/merge_result/',
        '',
        '- id: WriteStatus',
        '  type: Node',
        '  properties:',
        '    actor: !ref FileWriter',
        '    constants:',
        '      filename: restflow_status.txt',
        '    inflows:',
        '      message: /variable/clean_finished/',
        ]
    document = "\n".join(yaml_document)+"\n"
    with open("/home/tk/sandbox/restflow/rf_yaml.yaml", "w") as f:
        f.write(document)
    return document
