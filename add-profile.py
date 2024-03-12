"""
Add a "Profile Name" field to a bag, so that metadata can be added in Bagger.
"""

import bagit
import argparse
from os.path import exists, isdir

parser = argparse.ArgumentParser()
parser.add_argument('path', help='Path to bag directory')
args = parser.parse_args()

if not exists(args.path):
    print("Error:", args.path, "cannot be found")
    quit()
if not isdir(args.path):
    print("Error:", args.path, "is not a directory")
    quit()

print("Opening bag at", args.path, "...")
bag = bagit.Bag(args.path)
bag.info['Profile Name'] = 'Swarthmore-FHL'
bag.save()
print("Bag modified and saved!")