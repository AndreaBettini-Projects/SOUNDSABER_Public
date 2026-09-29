#ifndef IMU_H
#define IMU_H

void initIMU();
void resetIMUFilter();
void saber_commands();
void clean_coord();
void IMU_update();
void loadMagCalibration();
void saveMagCalibration();

#endif