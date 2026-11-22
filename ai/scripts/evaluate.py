"""Đánh giá mô hình trên tập test: confusion matrix, độ đo từng lớp, tốc độ suy luận (phần của C).

Tập test xếp theo thư mục, mỗi lớp một thư mục con, tên trùng với ai/models/labels.json:
    ai/data/test/giay/*.jpg
    ai/data/test/nhua/*.jpg
    ...

Chạy từ thư mục gốc repo:
    py ai/scripts/evaluate.py
    py ai/scripts/evaluate.py --test-dir "D:/duong/dan/test"

Kết quả ghi vào ai/reports/:
    summary.md            tóm tắt để chép vào báo cáo
    metrics.csv           precision, recall, F1, số ảnh từng lớp
    confusion_matrix.csv  ma trận nhầm lẫn (hàng = nhãn thật, cột = nhãn dự đoán)
    confusion_matrix.png  hình ma trận (cần matplotlib: py -m pip install matplotlib)
    misclassified.csv     danh sách ảnh bị đoán sai, để xem lại bằng mắt
"""
import argparse
import csv
import json
import platform
import time
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[2]
IMG_SIZE = (224, 224)
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def load_image(path: Path) -> np.ndarray:
    # Tiền xử lý giống hệt backend/app/routers/predict.py để số liệu đánh giá khớp với lúc chạy thật
    img = Image.open(path)
    return np.asarray(img.convert("RGB").resize(IMG_SIZE, Image.BILINEAR), dtype="float32")


def collect(test_dir: Path, labels: list):
    items, skipped = [], []
    for d in sorted(p for p in test_dir.iterdir() if p.is_dir()):
        if d.name not in labels:
            skipped.append(d.name)
            continue
        for f in sorted(d.rglob("*")):
            if f.suffix.lower() in EXTS:
                items.append((f, labels.index(d.name)))
    return items, skipped


def main():
    ap = argparse.ArgumentParser(description="Đánh giá mô hình phân loại rác trên tập test")
    ap.add_argument("--test-dir", default=str(ROOT / "ai" / "data" / "test"))
    ap.add_argument("--model", default=str(ROOT / "ai" / "models" / "smart_recycle_model.onnx"))
    ap.add_argument("--labels", default=str(ROOT / "ai" / "models" / "labels.json"))
    ap.add_argument("--out", default=str(ROOT / "ai" / "reports"))
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()

    import onnxruntime as ort

    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    n = len(labels)
    test_dir, out = Path(args.test_dir), Path(args.out)
    if not test_dir.is_dir():
        raise SystemExit(f"Không thấy thư mục test: {test_dir}")
    items, skipped = collect(test_dir, labels)
    if skipped:
        print("Bỏ qua thư mục không có trong labels.json:", ", ".join(skipped))
    if not items:
        raise SystemExit("Không có ảnh nào trong thư mục test.")

    sess = ort.InferenceSession(args.model, providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0].name
    n_out = sess.get_outputs()[0].shape[-1]
    if isinstance(n_out, int) and n_out != n:
        raise SystemExit(f"Mô hình có {n_out} lớp nhưng labels.json có {n} lớp.")

    # ---- Dự đoán toàn bộ tập test ----
    y_true, y_pred, conf, paths, bad = [], [], [], [], []
    for i in range(0, len(items), args.batch):
        batch, idx = [], []
        for f, t in items[i:i + args.batch]:
            try:
                batch.append(load_image(f))
                idx.append((f, t))
            except (UnidentifiedImageError, OSError):
                bad.append(f)
        if not batch:
            continue
        probs = sess.run(None, {inp: np.stack(batch)})[0]
        for (f, t), p in zip(idx, probs):
            k = int(np.argmax(p))
            y_true.append(t); y_pred.append(k); conf.append(float(p[k])); paths.append(f)
        print(f"  {min(i + args.batch, len(items))}/{len(items)} ảnh", end="\r")
    print()
    y_true, y_pred = np.array(y_true), np.array(y_pred)
    total = len(y_true)

    # ---- Ma trận nhầm lẫn và độ đo ----
    cm = np.zeros((n, n), dtype=int)
    for t, p in zip(y_true, y_pred):
        cm[t, p] += 1
    acc = float(np.trace(cm) / total)
    rows = []
    for k, name in enumerate(labels):
        tp = cm[k, k]
        support = int(cm[k].sum())
        pred_k = int(cm[:, k].sum())
        prec = tp / pred_k if pred_k else 0.0
        rec = tp / support if support else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        rows.append({"label": name, "support": support, "precision": prec, "recall": rec, "f1": f1})
    present = [r for r in rows if r["support"] > 0]
    macro_f1 = float(np.mean([r["f1"] for r in present])) if present else 0.0

    pairs = [(int(cm[a, b]), labels[a], labels[b]) for a in range(n) for b in range(n) if a != b and cm[a, b]]
    pairs.sort(reverse=True)

    # ---- Tốc độ: từng ảnh một trên CPU, giống backend xử lý một yêu cầu ----
    sample = load_image(paths[0])[None, ...]
    for _ in range(5):
        sess.run(None, {inp: sample})
    times = []
    for _ in range(50):
        t0 = time.perf_counter()
        sess.run(None, {inp: sample})
        times.append((time.perf_counter() - t0) * 1000)
    ms_mean, ms_p95 = float(np.mean(times)), float(np.percentile(times, 95))

    # ---- Ghi file ----
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "confusion_matrix.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["thật \\ dự đoán"] + labels)
        for k, name in enumerate(labels):
            w.writerow([name] + cm[k].tolist())
    with open(out / "metrics.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["label", "so_anh", "precision", "recall", "f1"])
        for r in rows:
            w.writerow([r["label"], r["support"], f"{r['precision']:.4f}", f"{r['recall']:.4f}", f"{r['f1']:.4f}"])
    with open(out / "misclassified.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["anh", "nhan_that", "du_doan", "do_tin_cay"])
        for f, t, p, c in zip(paths, y_true, y_pred, conf):
            if t != p:
                w.writerow([str(f), labels[t], labels[p], f"{c:.4f}"])

    png = False
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
        fig, ax = plt.subplots(figsize=(1.1 * n + 2, 1.1 * n + 1.5))
        ax.imshow(norm, cmap="Greens", vmin=0, vmax=1)
        ax.set_xticks(range(n), labels, rotation=45, ha="right")
        ax.set_yticks(range(n), labels)
        ax.set_xlabel("Nhãn dự đoán")
        ax.set_ylabel("Nhãn thật")
        ax.set_title(f"Ma trận nhầm lẫn (accuracy {acc:.2%}, {total} ảnh)")
        for a in range(n):
            for b in range(n):
                ax.text(b, a, cm[a, b], ha="center", va="center",
                        color="white" if norm[a, b] > 0.5 else "black", fontsize=9)
        fig.tight_layout()
        fig.savefig(out / "confusion_matrix.png", dpi=150)
        png = True
    except ImportError:
        print("Chưa có matplotlib nên không vẽ hình (py -m pip install matplotlib).")

    lines = [
        "# Kết quả đánh giá mô hình",
        "",
        f"- Mô hình: `{Path(args.model).name}`",
        f"- Tập test: `{test_dir}`, **{total} ảnh**, {len(present)} lớp có ảnh",
        f"- **Accuracy: {acc:.2%}**, Macro F1: {macro_f1:.4f}",
        f"- Tốc độ suy luận trên CPU ({platform.processor() or platform.machine()}), "
        f"1 ảnh/lần: trung bình **{ms_mean:.1f} ms**, p95 {ms_p95:.1f} ms (chưa tính đọc và resize ảnh)",
        "",
        "## Độ đo từng lớp",
        "",
        "| Lớp | Số ảnh | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    lines += [f"| {r['label']} | {r['support']} | {r['precision']:.3f} | {r['recall']:.3f} | {r['f1']:.3f} |" for r in rows]
    lines += ["", "## Các cặp hay nhầm nhất", ""]
    lines += [f"- `{a}` bị đoán thành `{b}`: {c} ảnh" for c, a, b in pairs[:8]] or ["- Không có ảnh nào bị đoán sai."]
    if bad:
        lines += ["", f"Có {len(bad)} ảnh không đọc được và đã bỏ qua."]
    if png:
        lines += ["", "![Ma trận nhầm lẫn](confusion_matrix.png)"]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Accuracy {acc:.2%} trên {total} ảnh, macro F1 {macro_f1:.4f}, {ms_mean:.1f} ms/ảnh trên CPU")
    print(f"Đã ghi kết quả vào {out}")


if __name__ == "__main__":
    main()
