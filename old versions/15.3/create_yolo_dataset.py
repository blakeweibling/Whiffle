import argparse
import random
import shutil
from pathlib import Path


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def list_images(input_dir):
    return sorted(
        [p for p in input_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS]
    )


def ensure_structure(output_dir, include_test):
    (output_dir / "images" / "train").mkdir(parents=True, exist_ok=True)
    (output_dir / "images" / "val").mkdir(parents=True, exist_ok=True)
    (output_dir / "labels" / "train").mkdir(parents=True, exist_ok=True)
    (output_dir / "labels" / "val").mkdir(parents=True, exist_ok=True)
    if include_test:
        (output_dir / "images" / "test").mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / "test").mkdir(parents=True, exist_ok=True)


def split_items(items, val_split, test_split, seed):
    rng = random.Random(seed)
    items = list(items)
    rng.shuffle(items)
    n_total = len(items)
    n_test = int(round(n_total * test_split))
    n_val = int(round(n_total * val_split))
    n_test = min(n_test, n_total)
    n_val = min(n_val, n_total - n_test)
    test_items = items[:n_test]
    val_items = items[n_test : n_test + n_val]
    train_items = items[n_test + n_val :]
    return train_items, val_items, test_items


def copy_or_move(src, dst, mode):
    if mode == "move":
        shutil.move(str(src), str(dst))
    elif mode == "copy":
        shutil.copy2(str(src), str(dst))
    else:
        raise ValueError(f"Unsupported mode: {mode}")


def write_empty_labels(items, labels_dir):
    for src in items:
        label_path = labels_dir / (src.stem + ".txt")
        label_path.touch(exist_ok=True)


def write_data_yaml(output_dir, class_names):
    lines = [
        f"path: {output_dir.resolve()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        f"nc: {len(class_names)}",
        "names:",
    ]
    for idx, name in enumerate(class_names):
        lines.append(f"  {idx}: {name}")
    (output_dir / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_dataset(
    input_dir,
    output_dir,
    val_split=0.15,
    test_split=0.0,
    seed=42,
    mode="copy",
    empty_labels=False,
    classes=None,
):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    images = list_images(input_dir)
    if not images:
        raise RuntimeError(f"No images found in {input_dir}")

    include_test = test_split > 0
    ensure_structure(output_dir, include_test)

    train_items, val_items, test_items = split_items(
        images, val_split, test_split, seed
    )

    for src in train_items:
        copy_or_move(src, output_dir / "images" / "train" / src.name, mode)
    for src in val_items:
        copy_or_move(src, output_dir / "images" / "val" / src.name, mode)
    for src in test_items:
        copy_or_move(src, output_dir / "images" / "test" / src.name, mode)

    if empty_labels:
        write_empty_labels(train_items, output_dir / "labels" / "train")
        write_empty_labels(val_items, output_dir / "labels" / "val")
        if include_test:
            write_empty_labels(test_items, output_dir / "labels" / "test")

    if classes is not None and len(classes) > 0:
        write_data_yaml(output_dir, classes)

    print(
        f"Created dataset at {output_dir} "
        f"(train={len(train_items)}, val={len(val_items)}, test={len(test_items)})"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Create a YOLO dataset structure and split images."
    )
    parser.add_argument("input_dir", help="Directory containing source images")
    parser.add_argument("output_dir", help="Output dataset directory")
    parser.add_argument(
        "--val-split",
        type=float,
        default=0.15,
        help="Validation split fraction (default: 0.15)",
    )
    parser.add_argument(
        "--test-split",
        type=float,
        default=0.0,
        help="Test split fraction (default: 0.0)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for shuffling (default: 42)",
    )
    parser.add_argument(
        "--mode",
        choices=["copy", "move"],
        default="copy",
        help="Copy or move images into the dataset (default: copy)",
    )
    parser.add_argument(
        "--empty-labels",
        action="store_true",
        help="Create empty label files matching each image",
    )
    parser.add_argument(
        "--classes",
        nargs="*",
        default=None,
        help="Class names to include in data.yaml (optional)",
    )
    args = parser.parse_args()

    create_dataset(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        val_split=args.val_split,
        test_split=args.test_split,
        seed=args.seed,
        mode=args.mode,
        empty_labels=args.empty_labels,
        classes=args.classes,
    )


if __name__ == "__main__":
    main()
