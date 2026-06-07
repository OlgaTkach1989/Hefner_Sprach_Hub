export type StaffProfile = {
  email: string;
  firstName: string;
  lastName: string;
  fullName: string;
  isTeacher: boolean;
  isAdmin: boolean;
  isSuperuser: boolean;
  teacherId: number | null;
};

export type StaffLoginResponse = {
  profile: StaffProfile;
};
