"""命令行入口：扫描、导出、自检。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .mask import ClassifiedTerm
from .mschxudp import verify_dat
from .pipeline import DEFAULT_OUTPUT_DIR, export_bundle, process_paths


def _open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}" 2>/dev/null || true')


def cmd_build(args: argparse.Namespace) -> int:
    paths = args.input or []
    if not paths:
        print("请指定 --input 文件或文件夹（仅授权路径）。", file=sys.stderr)
        return 2
    candidates, held = process_paths(paths)
    if args.all_candidates:
        for c in candidates:
            c.selected = True
    out = args.output or DEFAULT_OUTPUT_DIR
    result = export_bundle(
        candidates,
        held,
        out,
        include_dat=not args.tsv_only,
        candidate_pos=args.position,
    )
    print(f"候选: {result['candidate_count']}  暂扣: {result['held_count']}  .dat条数: {result['dat_count']}")
    print(f"输出目录: {result['output_dir']}")
    if result["dat"]:
        ok, msg = verify_dat(result["dat"])
        print(f".dat 校验: {'通过' if ok else '失败'} ({msg})")
    if args.open:
        _open_folder(Path(result["output_dir"]))
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    """构建示例 .dat 并检查 magic。"""
    from .mschxudp import MAGIC, build_dat, write_dat

    root = Path(__file__).resolve().parent.parent
    sample_dir = root / "sample"
    out_dir = Path(args.output) if args.output else root / "tests" / "_selftest_out"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 直接二进制构建
    data = build_dat(
        [
            ("微软拼音", "weiruanpinyin", 1),
            ("用户自定义短语", "yonghuzidingyiduanju", 1),
            ("001项目", "linglingyixiangmu", 1),
        ],
        timestamp=1700000000,
    )
    if data[:8] != MAGIC:
        print("FAIL: magic 不是 mschxudp", file=sys.stderr)
        return 1
    dat_path = out_dir / "selftest.dat"
    dat_path.write_bytes(data)
    ok, msg = verify_dat(dat_path)
    if not ok:
        print(f"FAIL: verify {msg}", file=sys.stderr)
        return 1
    print(f"PASS: 直接构建 .dat magic=mschxudp ({msg})")

    # 2) 经 sample 流水线
    if sample_dir.is_dir():
        cands, held = process_paths([sample_dir])
        for c in cands:
            c.selected = True
        result = export_bundle(cands, held, out_dir / "from_sample", include_dat=True)
        if result["dat"]:
            ok2, msg2 = verify_dat(result["dat"])
            if not ok2:
                print(f"FAIL: sample 流水线 {msg2}", file=sys.stderr)
                return 1
            print(
                f"PASS: sample 流水线 candidates={result['candidate_count']} "
                f"held={result['held_count']} dat={result['dat_count']} ({msg2})"
            )
        else:
            print("FAIL: 未生成 dat", file=sys.stderr)
            return 1
    else:
        print("WARN: 无 sample/ 目录，跳过流水线测试")

    print("SELFTEST PASS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="001Project-lexicon",
        description="001Project 微软拼音个人词库（本地、授权路径、默认导出不写 IME）",
    )
    p.add_argument("--version", action="version", version=f"001Project {__version__}")
    sub = p.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="从授权路径提取并导出")
    b.add_argument("--input", "-i", nargs="+", help="授权的文件或文件夹")
    b.add_argument("--output", "-o", help=f"输出目录（默认 {DEFAULT_OUTPUT_DIR}）")
    b.add_argument("--position", type=int, default=1, help="候选位置 1–9")
    b.add_argument("--tsv-only", action="store_true", help="只写 TSV，不写 .dat")
    b.add_argument("--all-candidates", action="store_true", help="导出全部非暂扣候选")
    b.add_argument("--open", action="store_true", help="导出后打开输出文件夹")
    b.set_defaults(func=cmd_build)

    t = sub.add_parser("selftest", help="自检：构建 .dat 并验证 magic")
    t.add_argument("--output", "-o", help="自检输出目录")
    t.set_defaults(func=cmd_selftest)

    g = sub.add_parser("gui", help="启动图形界面")
    g.set_defaults(func=lambda args: _run_gui())
    return p


def _run_gui() -> int:
    from .gui import main as gui_main

    gui_main()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        # 无子命令时优先 GUI
        return _run_gui()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
