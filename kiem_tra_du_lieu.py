"""KIỂM TRA LẠI CSV — bản .py để xem nhanh dữ liệu, không cần notebook.

Chạy sau pipeline.py: python kiem_tra_du_lieu.py
Chỉ đọc CSV và chạy lại kiểm định schema/giá trị S15, in mẫu và cờ chất lượng.
S14 và tính nguyên vẹn raw được pipeline kiểm tra khi xử lý nguồn, vì CSV
không chứa các dòng đã bị loại để tự đối chiếu lại nhật ký E2/E3.
Có thể chỉ định CSV khác bằng --csv-path.
"""

import argparse

import pandas as pd

from tien_xu_ly.buoc_00_cau_hinh import PipelineConfig, setup_logger
from tien_xu_ly.buoc_04_kiem_dinh import validate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Đọc và kiểm định lại CSV tiền xử lý")
    defaults = PipelineConfig()
    parser.add_argument("--csv-path", default=str(defaults.processed_dir / defaults.output_csv))
    args = parser.parse_args()
    try:
        data = pd.read_csv(args.csv_path)
        validate_dataset(data, setup_logger())
        print(f"\nBảng: {data.shape[0]:,} dòng × {data.shape[1]} cột")
        print("Số cờ end_unknown:", int(data["end_unknown"].sum()))
        print("Kết quả chuyền:", data["pass_outcome"].value_counts().to_dict())
        print("\n5 dòng đầu:\n", data.head().to_string(index=False))
    except (AssertionError, ValueError, OSError) as error:
        parser.exit(1, f"CSV chưa đạt: {error}\n")


if __name__ == "__main__":
    main()
