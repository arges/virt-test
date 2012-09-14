import os, logging, re
from autotest.client.shared import error
from virttest import utils_test


@error.context_aware
def run_multi_nics_verify(test, params, env):
    """
    Verify guest NIC numbers again whats provided in test config file.

    If the guest NICs info does not match whats in the params at first,
    try to fix these by operating the networking config file.
    1. Boot guest with multi NICs.
    2. Check whether guest NICs info match with params setting.
    3. Create configure file for every NIC interface in guest.
    4. Reboot guest.
    5. Check whether guest NICs info match with params setting.

    @param test: QEMU test object
    @param params: Dictionary with the test parameters
    @param env: Dictionary with test environment.
    """
    # A helper function for getting NICs counts from ifconfig output of guest
    def get_nics_list(session):
        s, o = session.get_command_status_output("ifconfig")
        if s != 0:
            raise error.TestError("Running command 'ifconfig' failed in guest"
                                  " with output %s" % o)

        logging.debug("The ifconfig ouput from guest is:\n%s" % o)

        nics_list = re.findall(r'eth(\d+)\s+Link', o, re.M)
        logging.info("NICs list: %s" % nics_list)

        return nics_list


    # A helper function for checking NICs number
    def check_nics_num(expect_c, session):
        txt = "Check whether guest NICs info match with params setting."
        error.context(txt, logging.info)
        nics_list = get_nics_list(session)
        actual_c = len(nics_list)
        msg = "Expect NICs nums are: %d\nPractical NICs nums are: %d\n" % \
                                                       (expect_c, actual_c)

        if not expect_c == actual_c:
            msg += "Nics count mismatch!\n"
            return (False, msg)
        return (True, msg+'Nics count match')


    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    session = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))
    # Redirect ifconfig output from guest to log file
    log_file = os.path.join(test.debugdir, "ifconfig")
    utils_test.dump_command_output(session, "ifconfig", log_file)

    # Get the ethernet cards number from params
    nics_num = len(params.objects("nics"))
    logging.info("[ %s ] NICs card specified in config file" % nics_num)

    # Pre-judgement for the ethernet interface
    logging.debug(check_nics_num(nics_num, session)[1])
    txt = "Create configure file for every NIC interface in guest."
    error.context(txt, logging.info)
    ifcfg_prefix = "/etc/sysconfig/network-scripts/ifcfg-eth"
    for num in range(nics_num):
        eth_config_path = "".join([ifcfg_prefix, str(num)])

        eth_config = """DEVICE=eth%s
BOOTPROTO=dhcp
ONBOOT=yes
""" % num

        cmd = "echo '%s' > %s" % (eth_config, eth_config_path)
        s, o = session.get_command_status_output(cmd)
        if s != 0:
            raise error.TestError("Failed to create ether config file: %s\n"
                                  "Reason is: %s" % (eth_config_path, o))

    # Reboot and check the configurations.
    new_session = vm.reboot(session)
    s, msg = check_nics_num(nics_num, new_session)
    if not s:
        raise error.TestFail(msg)

    # NICs matched.
    logging.info(msg)