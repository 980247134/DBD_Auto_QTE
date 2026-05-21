import numpy as np
import os

_o0 = False
try:
    import onnxruntime as ort
    _o0 = True
except ImportError:
    pass


def _i1() -> bool:
    return _o0


class _D3:
    _M0 = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    _S0 = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    _SC = (1.0 / 255.0) / _S0
    _BI = -_M0 / _S0
    _SCC = _SC[:, None, None]
    _BIC = _BI[:, None, None]

    _PD = {
        0: {"desc": "None", "desc_cn": "无", "hit": False},
        1: {"desc": "type-1 (ok)", "desc_cn": "类型1 (命中)", "hit": True},
        2: {"desc": "type-1 (near)", "desc_cn": "类型1 (接近)", "hit": True},
        3: {"desc": "type-1 (out)", "desc_cn": "类型1 (外部)", "hit": False},
        4: {"desc": "type-2 (ok)", "desc_cn": "类型2 (命中)", "hit": True},
        5: {"desc": "type-2 (out)", "desc_cn": "类型2 (外部)", "hit": False},
        6: {"desc": "type-3 (ok)", "desc_cn": "类型3 (命中)", "hit": True},
        7: {"desc": "type-3 (out)", "desc_cn": "类型3 (外部)", "hit": False},
        8: {"desc": "type-4 (ok)", "desc_cn": "类型4 (命中)", "hit": True},
        9: {"desc": "type-4 (edge)", "desc_cn": "类型4 (边界)", "hit": False},
        10: {"desc": "type-4 (out)", "desc_cn": "类型4 (外部)", "hit": False},
    }

    def __init__(self, model_path: str, num_threads: int = 4):
        if not _o0:
            raise RuntimeError("onnxruntime 未安装")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"配置文件不存在: {model_path}")
        self._mp = model_path
        self._nt = num_threads
        self._os = None
        self._in = None
        self._l0()

    def _l0(self):
        _so = ort.SessionOptions()
        _so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        _so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        _so.intra_op_num_threads = self._nt
        _so.inter_op_num_threads = 1
        self._os = ort.InferenceSession(
            self._mp,
            providers=['CPUExecutionProvider'],
            sess_options=_so
        )
        self._in = self._os.get_inputs()[0].name
        _ii = self._os.get_inputs()[0]
        self._ish = list(_ii.shape)
        for _i, _d in enumerate(self._ish):
            if not isinstance(_d, int) or _d <= 0:
                self._ish[_i] = 1
        self._ib = np.empty(self._ish, dtype=np.float32)

    def _p0(self, _img):
        _r = np.transpose(_img, (2, 0, 1)).astype(np.float32)
        np.multiply(_r, self._SCC, out=self._ib[0])
        np.add(self._ib[0], self._BIC, out=self._ib[0])

    @staticmethod
    def _s0(_x: np.ndarray) -> np.ndarray:
        _e = np.exp(_x - np.max(_x))
        return _e / np.sum(_e)

    def _p1(self, _frame, _ct: float = 0.0) -> tuple:
        self._p0(_frame)
        _out = self._os.run(None, {self._in: self._ib})
        _lg = np.squeeze(_out)
        _pd = int(np.argmax(_lg))
        _pb = self._s0(_lg)
        _cf = float(_pb[_pd])
        _pdict = {self._PD[_i]["desc_cn"]: float(_pb[_i]) for _i in range(len(_pb))}
        _sh = self._PD[_pd]["hit"] and _cf >= _ct
        _dc = self._PD[_pd]["desc_cn"]
        return _sh, _pd, _dc, _pdict, _cf

    def _c0(self) -> str:
        if self._os is None:
            return "未加载"
        return "CPU"

    def _c1(self):
        if self._os is not None:
            del self._os
            self._os = None
        self._in = None

    @staticmethod
    def _s1(_md: str = "models") -> list:
        if not os.path.exists(_md):
            return []
        _rl = []
        for _f in sorted(os.listdir(_md)):
            if _f.endswith(".onnx"):
                _rl.append({"name": _f, "path": os.path.join(_md, _f)})
        return _rl