# Contributing

Thanks for helping improve Sorter Lab. Keep changes focused and make process behavior reproducible.

1. Create a virtual environment and install the editable package with `python -m pip install -e .`.
2. Run `python -m unittest discover -s tests -v` before opening a pull request.
3. For control changes, add a test describing the sampled inputs, controller state, outputs and resulting plant behavior.
4. Update the I/O map, API or engineering notes when public behavior changes.

Please do not present simulator behavior as a validated safety function or connect the project to live machinery.
