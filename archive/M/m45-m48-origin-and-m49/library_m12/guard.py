"""M12 适配器：原 M8 文件不改动；矛盾后旧证书必须失效。"""
from library_m8.core import PolynomialReader


class RevocableReader(PolynomialReader):
    def observe(self, x, value):
        # 原观测内容已矛盾时，不让异常处理后的调用者继续取得全域证书。
        if type(x) is int and x in self.evidence and type(value) is int and value in (0, 1) and self.evidence[x] != value:
            self.ledger.add('contradiction', 'Worker/paired-sensor',
                            {'x': x, 'old': self.evidence[x], 'new': value},
                            refs=(() if self.last_claim is None else (self.last_claim,)))
            self.ledger.revoke(self.assumption, 'stationarity/noise assumption contradicted')
            self.failed = True
            raise ValueError('contradictory evidence: prior certification revoked')
        return super().observe(x, value)
