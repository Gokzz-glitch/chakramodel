import argparse
import cv2
import torch
import numpy as np
from ultralytics import YOLO
from torchvision.models.detection import fasterrcnn_resnet50_fpn
from torchvision.transforms import functional as F


def iou_xyxy(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    iw = max(0, inter_x2 - inter_x1)
    ih = max(0, inter_y2 - inter_y1)
    inter = iw * ih
    ua = max(1, (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter)
    return inter / ua


class HybridRefiner:
    def __init__(self, yolo_weights, yolo_conf=0.25, uncertain_th=0.45, device="cpu"):
        self.yolo = YOLO(yolo_weights)
        self.yolo_conf = yolo_conf
        self.uncertain_th = uncertain_th
        self.device = device

        self.rcnn = fasterrcnn_resnet50_fpn(weights="DEFAULT").to(device).eval()

    @torch.no_grad()
    def refine(self, frame):
        result = self.yolo.predict(frame, conf=self.yolo_conf, verbose=False)[0]
        final = []

        if result.boxes is None or len(result.boxes) == 0:
            return final

        for b in result.boxes:
            x1, y1, x2, y2 = b.xyxy[0].cpu().numpy().astype(int).tolist()
            yscore = float(b.conf[0].cpu().numpy())

            if yscore >= self.uncertain_th:
                final.append(([x1, y1, x2, y2], yscore, "yolo"))
                continue

            h, w = frame.shape[:2]
            px = int(0.1 * (x2 - x1))
            py = int(0.1 * (y2 - y1))
            rx1 = max(0, x1 - px)
            ry1 = max(0, y1 - py)
            rx2 = min(w - 1, x2 + px)
            ry2 = min(h - 1, y2 + py)
            roi = frame[ry1:ry2, rx1:rx2]

            if roi.size == 0:
                final.append(([x1, y1, x2, y2], yscore, "yolo_fallback"))
                continue

            img_t = F.to_tensor(cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)).to(self.device)
            out = self.rcnn([img_t])[0]

            if len(out["boxes"]) == 0:
                final.append(([x1, y1, x2, y2], yscore, "yolo_fallback"))
                continue

            ridx = int(torch.argmax(out["scores"]).item())
            rscore = float(out["scores"][ridx].item())
            rb = out["boxes"][ridx].cpu().numpy().astype(int).tolist()
            fx1, fy1, fx2, fy2 = rb[0] + rx1, rb[1] + ry1, rb[2] + rx1, rb[3] + ry1

            if rscore > yscore and iou_xyxy([x1, y1, x2, y2], [fx1, fy1, fx2, fy2]) > 0.1:
                final.append(([fx1, fy1, fx2, fy2], rscore, "rcnn_refined"))
            else:
                final.append(([x1, y1, x2, y2], yscore, "yolo_kept"))

        return final


def draw(frame, dets):
    for box, score, tag in dets:
        x1, y1, x2, y2 = box
        color = (0, 255, 0) if "yolo" in tag else (255, 200, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"{tag}:{score:.2f}", (x1, max(20, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    return frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--yolo_weights", required=True)
    ap.add_argument("--out", default="outputs/hybrid_demo.mp4")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--uncertain_th", type=float, default=0.45)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = HybridRefiner(args.yolo_weights, args.conf, args.uncertain_th, device=device)

    cap = cv2.VideoCapture(args.source)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        dets = model.refine(frame)
        frame = draw(frame, dets)
        writer.write(frame)

    cap.release()
    writer.release()
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()