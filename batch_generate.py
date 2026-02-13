from generate_weekly_lesson import load_data, generate_html
from validate_week_1 import validate_html
import sys

def run_batch():
    # Loop from Week 2 to Week 10
    start_week = 2
    end_week = 10

    print(f"Starting batch generation for Week {start_week} to {end_week}...")

    failed_weeks = []

    for week in range(start_week, end_week + 1):
        try:
            print(f"\n--- Generating Week {week} ---")
            curr, vocab, hw = load_data(week)
            generate_html(week, curr, vocab, hw)

            output_file = f"Week_{week}_Lesson_Plan.html"
            print(f"Validating {output_file}...")
            # We call validate_html directly. It prints to stdout and exits on error.
            # We should wrap it to catch SystemExit if we want to continue.
            try:
                validate_html(output_file)
            except SystemExit as e:
                if e.code != 0:
                    print(f"Validation FAILED for Week {week}.")
                    failed_weeks.append(week)
                else:
                    print(f"Validation PASSED for Week {week}.")
            except Exception as e:
                print(f"Validation ERROR: {e}")
                failed_weeks.append(week)

        except Exception as e:
            print(f"Generation FAILED for Week {week}: {e}")
            failed_weeks.append(week)

    print("\n==================================")
    if failed_weeks:
        print(f"Batch completed with errors. Failed weeks: {failed_weeks}")
        sys.exit(1)
    else:
        print(f"Batch completed successfully for Weeks {start_week}-{end_week}.")
        sys.exit(0)

if __name__ == "__main__":
    run_batch()
