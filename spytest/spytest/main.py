import os
import sys
import time
import argparse
import pytest
import pyfiglet

from spytest.version import get_git_ver
from spytest.framework import parse_batch_args
from spytest.framework import parse_suite_files
import spytest.env as env

import utilities.common as utils

# 显示横幅的内容
'''
 ____  ____       _____         _
/ ___||  _ \ _   |_   _|__  ___| |_
\___ \| |_) | | | || |/ _ \/ __| __|
 ___) |  __/| |_| || |  __/\__ \ |_
|____/|_|    \__, ||_|\___||___/\__|
             |___/
'''
def _banner():
    result = pyfiglet.figlet_format("SPyTest")
    print(result)

# 显示当前所用 source code 的 branch 名称及 commitID
# VERSION: master e3258fe13ae054246c67980af7acf5174df935c3
def _print_git_ver():
    sha = get_git_ver()
    print("\nVERSION: {}\n".format(sha))

# 解析命令行参数
def _parse_args(pre_parse=False):

# 建立一个 argparse.ArgumentParser 对象的实例化
    # pytest hack to let it wotk with absolute paths for testbed and tclist
    parser = argparse.ArgumentParser(description='Process SpyTest arguments.',
                                     add_help=False)

# 添加参数
    if pre_parse:
        parser.add_argument("--args-file", action="store", default=None,
                            help="spytest arguments from file path")
    parser.add_argument("--testbed-file", action="store", default=None,
                        help="testbed file path -- default: ./testbed.yaml")
    parser.add_argument("--test-suite", action="append",
                        default=[], help="test suites")
    parser.add_argument("--test-paths", action="append",
                        default=[], help="test paths")
    parser.add_argument("--tclist-file", action="append",
                        default=None, help="test case list file path")
    parser.add_argument("--logs-path", action="store",
                        default=None, help="logs folder -- default: .")
    parser.add_argument("--logs-level", action="store",
                        default="info", help="logs level -- default: info")
    parser.add_argument("--log-level", action="store", dest="logs_level",
                        default="info", help="logs level -- default: info")
    parser.add_argument("--results-prefix", action="store",
                        default=None, help="Prefix to be used for results.")
    parser.add_argument("--file-mode", action="store_true", default=False,
                        help="Execute in file mode -- default: false")
    parser.add_argument("-n", "--numprocesses", action="store", default=None,
                        type=int, help="number of preocessese")
    parser.add_argument("--tclist-bucket", action="append", default=None,
                        help="use test cases from buckets")
    for bucket in range(1,9):
        parser.add_argument("--bucket-{}".format(bucket), action="store", default=None, nargs="*",
                            help="needed topology for bucket-{}.".format(bucket))
    parser.add_argument("--env", action="append", default=[],
                        nargs=2, help="environment variables")
    parser.add_argument("--exclude-devices", action="store", default=None,
                    help="exclude given duts from testbed")
    parser.add_argument("--include-devices", action="store", default=None,
                    help="include given duts from testbed")
    parser.add_argument("--open-config-api", action="store", default='GNMI',
                        help="specified open-config request API type -- default: gNMI")
    parser.add_argument("--noop", action="store_true", default=False,
                        help="No operation, to be used while using optional arguments")
    parser.add_argument("--augment-modules-csv", action="append", default=[], nargs="*",
                        help="Add additional lines to modules.csv")

# 解析参数，并分别存储已声明的，和未声明的
    args, unknown = parser.parse_known_args()

    # parse the bucket options
    argsdict = vars(args)
    tclist_bucket = ",".join(argsdict["tclist_bucket"] or "")
    bucket_list = []
    for bucket in range(1, 9):
        value = argsdict["bucket_{}".format(bucket)]
        if value is None: continue
        bucket_list.append(str(bucket))
        tclist_bucket = ",".join(bucket_list)
        if not value: continue
        os.environ["SPYTEST_TOPO_{}".format(bucket)] = " ".join(value)

    # update sys.argv with arguments from suite args
    if args.test_suite:
        addl_args = parse_suite_files(args.test_suite)
        index = sys.argv.index("--test-suite")
        new_argv = []
        new_argv.extend(sys.argv[:index])
        new_argv.extend(addl_args)
        new_argv.extend(sys.argv[index+2:])
        sys.argv = new_argv
        print("\nSuite Arguments {}\n".format(" ".join(addl_args)))
        print("\nExpanded Arguments {}\n".format(" ".join(sys.argv)))
        os.environ["SPYTEST_SUITE_ARGS"] = " ".join(addl_args)
        return _parse_args(pre_parse=pre_parse)

    if pre_parse and args.args_file:
        # read arguments from file
        user_root = env.get("SPYTEST_USER_ROOT")
        if user_root and not os.path.isabs(args.args_file):
            filepath = os.path.join(user_root, args.args_file)
        else:
            filepath = args.args_file
        file_args = []
        for line in utils.read_lines(filepath):
            file_args.extend(utils.split_with_quoted_strings(line))

        # update sys.argv with arguments from file
        index = sys.argv.index("--args-file")
        new_argv = []
        new_argv.extend(sys.argv[:index])
        new_argv.extend(file_args)
        new_argv.extend(sys.argv[index+2:])
        sys.argv = new_argv

        # update SPYTEST_CMDLINE_ARGS with arguments from file
        app_cmdline = env.get("SPYTEST_CMDLINE_ARGS", "")
        app_args = utils.split_with_quoted_strings(app_cmdline)
        index = app_args.index("--args-file")
        app_new_args = []
        app_new_args.extend(app_args[:index])
        for arg in file_args:
            app_new_args.append("'{}'".format(arg) if " " in arg else arg)
        app_new_args.extend(app_args[index+2:])
        os.environ["SPYTEST_CMDLINE_ARGS"] = " ".join(app_new_args)

        return _parse_args()

# 重置变量 ‘’ 中的参数，保留命令及未声明的参数
    sys.argv = [sys.argv[0]]
    sys.argv.extend(unknown)

    for name, value in args.env:
        print("setting environment {} = {}".format(name, value))
        os.environ[name] = value

    if args.exclude_devices:
        os.environ["SPYTEST_TESTBED_EXCLUDE_DEVICES"] = args.exclude_devices
        sys.argv.extend(["--exclude-devices", args.exclude_devices])
    if args.include_devices:
        os.environ["SPYTEST_TESTBED_INCLUDE_DEVICES"] = args.include_devices
        sys.argv.extend(["--include-devices", args.include_devices])
    if args.testbed_file:
        os.environ["SPYTEST_TESTBED_FILE"] = args.testbed_file
    if args.tclist_file:
        os.environ["SPYTEST_TCLIST_FILE"] = ",".join(args.tclist_file)

# 建立与 log 相关的环境变量 "SPYTEST_LOGS_PATH" "SPYTEST_LOGS_LEVEL"，并赋值
    if args.logs_path:
        os.environ["SPYTEST_LOGS_PATH"] = args.logs_path
    os.environ["SPYTEST_LOGS_LEVEL"] = args.logs_level

# 向环境变量 "SPYTEST_OPENCONFIG_API" 赋值
    if args.open_config_api:
        os.environ["SPYTEST_OPENCONFIG_API"] = args.open_config_api

# 向环境变量 "SPYTEST_TEST_PATHS" 赋值
    if args.test_paths:
        os.environ["SPYTEST_TEST_PATHS"] = ",".join(args.test_paths)

# 向环境变量 "SPYTEST_FILE_PREFIX" 赋值
    prefix=""
    prefix="results"
    if args.results_prefix:
        file_prefix = args.results_prefix
    elif args.file_mode and prefix:
        file_prefix = prefix
    elif tclist_bucket:
        file_prefix = prefix
    elif prefix:
        file_prefix = "{}_{}".format(prefix, time.strftime("%Y_%m_%d_%H_%M_%S"))
    else:
        file_prefix = "{}".format(time.strftime("%Y_%m_%d_%H_%M_%S"))
    os.environ["SPYTEST_FILE_PREFIX"] = file_prefix

    # filemode is needed in more places
    if args.file_mode:
        os.environ["SPYTEST_FILE_MODE"] = "1"
        sys.argv.append("--file-mode")

    addl_args = parse_batch_args(args.numprocesses, tclist_bucket, args.augment_modules_csv)
    sys.argv.extend(addl_args)

# 生成随机数，并将其存储到环境变量 ‘SPYTEST_RAMDOM_SEED’ 中。
    seed = utils.get_random_seed()
    print("SPYTEST_RAMDOM_SEED used = {}".format(seed))

'''
参数：sys.argv，采用数据类型-列表 [] 的方式存储；
参数：os.environ, 采用数据类型-字典 {} 的方式存储；
参数：args，采用数据类型-元组 () 的方式存储；
'''

    return args

def main(silent=False):
    if not silent:
        _banner()
    _parse_args(True)
    if not silent:
        _print_git_ver()
'''
The pytest module is from the ActivPython 'ActivPython/2.7.14/lib/python2.7/site-packages'.
Review the pytest.py module, the pytest.main() -> 'main' from the module '_pytest.config'.
'main' -> '__init__.py' in the directory '_pytest/config'.
    config = _prepareconfig ...
    config.hook.pytest_cmdline_main ...
        'pytest_cmdline_main' -> _pytest/main.py
            'wrap_session' -> _pytest/main.py
'''
    retval = pytest.main()
    return retval


