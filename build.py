import parse_data
import time
import sys

def build_all():
    print("Starting build for weeks 1-40...")
    start_time = time.time()

    success_count = 0
    errors = []

    for week in range(1, 41):
        try:
            print(f"--- Generating Week {week} ---")
            parse_data.main(week)
            success_count += 1
        except Exception as e:
            print(f"❌ Error generating Week {week}: {e}")
            errors.append(week)

    end_time = time.time()
    duration = end_time - start_time

    print("\n" + "="*30)
    print(f"Build Complete in {duration:.2f} seconds.")
    print(f"Success: {success_count}/40")
    if errors:
        print(f"Failed Weeks: {errors}")
    else:
        print("🎉 All weeks generated successfully!")
    print("="*30)

if __name__ == "__main__":
    build_all()
