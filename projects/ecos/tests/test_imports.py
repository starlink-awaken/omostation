"""eCOS 导入验证 — 核心模块可正常导入"""


def test_core_imports():
    from ecos.protocol.emergence import calc_emergence
    from ecos.common import common
    from ecos.protocol.ssb import ssb_client

    assert common.ECOS_HOME
    assert ssb_client
    assert calc_emergence


def test_common_paths():
    from ecos.common.common import ECOS_HOME, SSB_DB_PATH, TZ

    assert ECOS_HOME
    assert SSB_DB_PATH
    assert TZ


def test_ssb_init():
    from ecos.protocol.ssb.ssb_init import main as ssb_init

    assert callable(ssb_init)
