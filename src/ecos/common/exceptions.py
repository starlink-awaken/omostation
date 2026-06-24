"""ECOS 统一异常类型"""


class ECOSException(Exception):
    """ECOS 基础异常"""

    pass


class SyncException(ECOSException):
    """同步异常"""

    pass


class ConsensusException(ECOSException):
    """共识异常"""

    pass


class GraphException(ECOSException):
    """图谱异常"""

    pass


class TransportException(ECOSException):
    """传输异常"""

    pass


class ConfigException(ECOSException):
    """配置异常"""

    pass


class SecurityException(ECOSException):
    """安全异常"""

    pass


class PersistenceException(ECOSException):
    """持久化异常"""

    pass
