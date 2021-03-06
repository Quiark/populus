import os
import subprocess
import itertools
import yaml
import re


class CompileError(Exception):
    pass


SOLC_BINARY = 'solc'


version_regex = re.compile('Version: ([0-9]+\.[0-9]+\.[0-9]+(-[a-f0-9]+)?)')


def is_solc_available():
    program = 'solc'

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath = os.path.dirname(program)
    if fpath:
        if is_exe(program):
            return True
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return True

    return False


def solc_version():
    version_string = subprocess.check_output(['solc', '--version'])
    version = version_regex.search(version_string).groups()[0]
    return version


def solc(source=None, input_files=None, add_std=True,
         combined_json='json-abi,binary,sol-abi,natspec-dev,natspec-user',
         raw=False, rich=True):

    if source and input_files:
        raise ValueError("`source` and `input_files` are mutually exclusive")
    elif source is None and input_files is None:
        raise ValueError("Must provide either `source` or `input_files`")

    command = ['solc']
    if add_std:
        command.append('--add-std=1')

    if combined_json:
        command.extend(('--combined-json', combined_json))

    if input_files:
        command.extend(itertools.chain(*zip(itertools.repeat('--input-file'), input_files)))

    p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    if source:
        stdoutdata, stderrdata = p.communicate(input=source)
    else:
        stdoutdata, stderrdata = p.communicate()

    if p.returncode:
        raise CompileError('compilation failed')

    if raw:
        return stdoutdata

    contracts = yaml.safe_load(stdoutdata)['contracts']

    for contract_name, data in contracts.items():
        data['json-abi'] = yaml.safe_load(data['json-abi'])
        data['sol-abi'] = yaml.safe_load(data['sol-abi'])
        data['natspec-dev'] = yaml.safe_load(data['natspec-dev'])
        data['natspec-user'] = yaml.safe_load(data['natspec-user'])

    sorted_contracts = sorted(contracts.items(), key=lambda c: c[0])

    if not rich:
        return sorted_contracts

    compiler_version = solc_version()

    return {
        contract_name: {
            'code': "0x" + contract.get('binary'),
            'info': {
                'abiDefinition': contract.get('json-abi'),
                'compilerVersion': compiler_version,
                'developerDoc': contract.get('natspec-dev'),
                'language': 'Solidity',
                'languageVersion': '0',
                'source': source,  # what to do for files?
                'userDoc': contract.get('natspec-user')
            },
        }
        for contract_name, contract
        in sorted_contracts
    }
