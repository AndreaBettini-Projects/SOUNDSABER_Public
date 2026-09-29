import os
import shutil
from sklearn.model_selection import train_test_split
from config import TRAIN_RATIO, TST2VAL_RATIO

def split_train_val_test(orig_dir, train_orig_dir, val_dir, test_dir, random_state=42, train_ratio=TRAIN_RATIO):

    # create the train, val, and test directories if they don't exist
    os.makedirs(train_orig_dir, exist_ok=True)
    os.makedirs(val_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)

    # create list of keywords taking the names of only the folders in the Original directory
    keywords = [d for d in os.listdir(orig_dir) if os.path.isdir(os.path.join(orig_dir, d))] 
    keywords = [k for k in keywords if k not in ["Archive"]] # include Unknown, exclude Archive
    for keyword in keywords:

        # from a "source" directory for the specific keyword...
        source_dir = os.path.join(orig_dir, keyword)
        # ..list all the .wav files in that directory
        files = [f for f in os.listdir(source_dir) if f.endswith(".wav")]

        train_orig_files, temp_files = train_test_split(
            files,
            test_size=1-train_ratio,
            random_state=random_state,
            shuffle=True,

        )

        val_files, test_files = train_test_split(
            temp_files,
            test_size=TST2VAL_RATIO,
            random_state=random_state,
            shuffle=True,
        )

        # creates dictionary to map destination directories to their corresponding file lists
        splits = {
            train_orig_dir: train_orig_files,
            val_dir: val_files,
            test_dir: test_files
        }

        for destination, subset in splits.items(): # destination is e.g. "TRAIN_ORIG_DIR", subset is the list of files e.g. "train_files"

            keyword_dir = os.path.join(destination, keyword)
            os.makedirs(keyword_dir, exist_ok=True)

            # now copy the original files to the corresponding train or val or test directories
            for file in subset:
                shutil.copy(os.path.join(source_dir, file), os.path.join(keyword_dir, file)) 

        print(f"{keyword}:")
        print(f"  Train      : {len(train_orig_files)}")
        print(f"  Validation : {len(val_files)}")
        print(f"  Test       : {len(test_files)}")

    print("\nDataset split complete.")