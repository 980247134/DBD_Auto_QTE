import numpy as np
import os

_onnxruntime_available = False
try:
    import onnxruntime as ort
    _onnxruntime_available = True
except ImportError:
    pass


def is_onnxruntime_available() -> bool:
    return _onnxruntime_available


class AIDetector:
    """
    ONNX model inference wrapper for DBD skill check detection.

    Adapted from Manuteaa/dbd_autoSkillCheck AI_model.py.
    Uses MobileNet V3 Small to classify skill check frames into 11 categories.
    """

    MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    PRED_DICT = {
        0: {"desc": "None", "desc_cn": "无", "hit": False},
        1: {"desc": "repair-heal (great)", "desc_cn": "修复/治疗 (完美)", "hit": True},
        2: {"desc": "repair-heal (ante-frontier)", "desc_cn": "修复/治疗 (接近)", "hit": True},
        3: {"desc": "repair-heal (out)", "desc_cn": "修复/治疗 (外部)", "hit": False},
        4: {"desc": "full white (great)", "desc_cn": "全白 (完美)", "hit": True},
        5: {"desc": "full white (out)", "desc_cn": "全白 (外部)", "hit": False},
        6: {"desc": "full black (great)", "desc_cn": "全黑 (完美)", "hit": True},
        7: {"desc": "full black (out)", "desc_cn": "全黑 (外部)", "hit": False},
        8: {"desc": "wiggle (great)", "desc_cn": "挣扎 (完美)", "hit": True},
        9: {"desc": "wiggle (frontier)", "desc_cn": "挣扎 (边界)", "hit": False},
        10: {"desc": "wiggle (out)", "desc_cn": "挣扎 (外部)", "hit": False},
    }

    ANTE_FRONTIER_CLASS = 2

    def __init__(self, model_path: str, use_gpu: bool = False, nb_cpu_threads: int = None):
        if not _onnxruntime_available:
            raise RuntimeError(
                "onnxruntime 未安装。请运行: pip install onnxruntime"
            )
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        self.model_path = model_path
        self.use_gpu = use_gpu
        self.nb_cpu_threads = nb_cpu_threads
        self.ort_session = None
        self.input_name = None
        self._load_model()

    def _load_model(self):
        sess_options = ort.SessionOptions()
        if not self.use_gpu and self.nb_cpu_threads is not None:
            sess_options.intra_op_num_threads = self.nb_cpu_threads
            sess_options.inter_op_num_threads = self.nb_cpu_threads

        if self.use_gpu:
            available = ort.get_available_providers()
            preferred = ['CUDAExecutionProvider', 'DmlExecutionProvider', 'CPUExecutionProvider']
            providers = [p for p in preferred if p in available]
        else:
            providers = ["CPUExecutionProvider"]

        self.ort_session = ort.InferenceSession(
            self.model_path, providers=providers, sess_options=sess_options
        )
        self.input_name = self.ort_session.get_inputs()[0].name

    def _preprocess(self, img_rgb: np.ndarray) -> np.ndarray:
        img = np.asarray(img_rgb, dtype=np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
        img = (img - self.MEAN[:, None, None]) / self.STD[:, None, None]
        img = np.expand_dims(img, axis=0)
        return np.ascontiguousarray(img)

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        exp_x = np.exp(x - np.max(x))
        return exp_x / np.sum(exp_x)

    def predict(self, frame_rgb_224: np.ndarray) -> tuple:
        input_tensor = self._preprocess(frame_rgb_224)
        output = self.ort_session.run(None, {self.input_name: input_tensor})
        logits = np.squeeze(output)
        pred = int(np.argmax(logits))
        probs = self._softmax(logits)
        probs_dict = {self.PRED_DICT[i]["desc_cn"]: float(probs[i]) for i in range(len(probs))}
        should_hit = self.PRED_DICT[pred]["hit"]
        desc_cn = self.PRED_DICT[pred]["desc_cn"]
        is_ante_frontier = (pred == self.ANTE_FRONTIER_CLASS)
        return should_hit, pred, desc_cn, probs_dict, is_ante_frontier

    def check_provider(self) -> str:
        if self.ort_session is None:
            return "未加载"
        providers = self.ort_session.get_providers()
        if "CUDAExecutionProvider" in providers:
            return "GPU (CUDA)"
        elif "DmlExecutionProvider" in providers:
            return "GPU (DirectML)"
        return "CPU"

    def cleanup(self):
        if self.ort_session is not None:
            del self.ort_session
            self.ort_session = None
        self.input_name = None

    @staticmethod
    def scan_models(models_dir: str = "models") -> list:
        if not os.path.exists(models_dir):
            return []
        results = []
        for f in sorted(os.listdir(models_dir)):
            if f.endswith(".onnx") or f.endswith(".trt"):
                results.append({"name": f, "path": os.path.join(models_dir, f)})
        return results
