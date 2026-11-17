# README

# Scanning Procedure
1. connect and power on the camera and turntable.
    - the turntable controller (parker zeta 6104) is connected to the turntable, pc (com2) and power.
    - the camera(s) is connected to the network switch and power
2. launch the camera control software (cognex/keyence) and setup the recording options
    - adjust the capture settings
    - set the location to save recorded images
    - hit the record button the save images to the save location (instead of on the camera device or dedicated ftp procedure)
3. launch the python control program that controls the turntable and camera trigger
    - activate the virtual environment
      ```
      . .venv/Scripts/Activate.ps1

      . .venv/bin/activate
      ```
    - run `python <program name>.py`
      ```
      # 20261117
      python demo.py
      ```
4. rename and output files and add metadata
    - alter the active directory that the renaming script operates on
    - run the renaming script
      ```
      python fileRename2.py

      python Keyence_fileRenaming.py
      ```

