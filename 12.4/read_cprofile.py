import pstats
from pstats import SortKey

# Load the statistics
p = pstats.Stats('profile_output.prof')

# Sort and print the top 20 functions by cumulative time
# (Time spent in the function itself + time in functions it called)
print("--- Top 20 by Cumulative Time ---")
p.sort_stats(SortKey.CUMULATIVE).print_stats(20)

# Sort and print the top 20 functions by total time
# (Time spent ONLY within the function, excluding sub-calls)
print("\n--- Top 20 by Total Time (tottime) ---")
p.sort_stats(SortKey.TIME).print_stats(20) # SortKey.TIME is equivalent to 'tottime'

# You can also sort by number of calls: SortKey.CALLS