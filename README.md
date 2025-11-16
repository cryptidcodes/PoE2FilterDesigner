# PoE2FilterDesigner
tool for generating filters for Path of Exile 2

## Deprecated
Neversink's filterblade was updated to support PoE 2, including custom functionality that this project provided beyond the previous functionality available in filterblade. As such, this project will no longer be supported.

## Version Info

v0.1.2
Changes:
fixed repo to contain source code instead of zip.

v0.1.1
Changes:
Updated filterbase to use current version of NeverSink's LiteFilter.
Made the bat attempt to use py installer this (should?) prevent needing to check the box to add python to PATH.
Set Hide option to False by default.

===================

Installation:
1. Make sure Python 3.7 or later is installed on your system
2. Run setup.bat to set up the program (optional, as long as you didn't move any of the files in the subdirectories around)
3. Edit filtersettings.txt to customize your filter settings

Usage:
1. Open filtersettings.txt in any text editor (like Notepad)
2. Set the items you want to show to "True"
3. Save filtersettings.txt
4. Right click PoE2Filter.py > Open With > Python (if that doesnt work, try running run_filter.bat)
5. The generated filter will be in POE2FilterDesigner\filter.filter

Copy this file to your Path of Exile 2 filter directory to use it in-game.
