"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import {
  UserResponse,
  OrganizationResponse,
  UserRegisterRequest,
  UserLoginRequest,
  getAuthToken,
  setAuthToken,
  getActiveOrgId,
  setActiveOrgId,
  registerUser as apiRegister,
  loginUser as apiLogin,
  logoutUser as apiLogout,
  fetchMe,
} from "./api";

interface AuthContextType {
  user: UserResponse | null;
  organization: OrganizationResponse | null;
  organizations: OrganizationResponse[];
  token: string | null;
  isLoading: boolean;
  login: (req: UserLoginRequest) => Promise<void>;
  register: (req: UserRegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  switchOrganization: (orgId: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [organization, setOrganization] = useState<OrganizationResponse | null>(null);
  const [organizations, setOrganizations] = useState<OrganizationResponse[]>([]);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshProfile = useCallback(async () => {
    const existingToken = getAuthToken();
    if (!existingToken) {
      setUser(null);
      setOrganization(null);
      setOrganizations([]);
      setToken(null);
      setIsLoading(false);
      return;
    }

    try {
      setToken(existingToken);
      const profile = await fetchMe();
      setUser(profile.user);
      setOrganization(profile.organization);
      setOrganizations(profile.organizations);
      setActiveOrgId(profile.organization.id);
    } catch (err) {
      console.warn("Failed to load user session, resetting auth token:", err);
      setAuthToken(null);
      setActiveOrgId(null);
      setUser(null);
      setOrganization(null);
      setOrganizations([]);
      setToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshProfile();
  }, [refreshProfile]);

  const login = async (req: UserLoginRequest) => {
    setIsLoading(true);
    try {
      const resp = await apiLogin(req);
      setUser(resp.user);
      setOrganization(resp.organization);
      setToken(resp.access_token);
      await refreshProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (req: UserRegisterRequest) => {
    setIsLoading(true);
    try {
      const resp = await apiRegister(req);
      setUser(resp.user);
      setOrganization(resp.organization);
      setToken(resp.access_token);
      await refreshProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await apiLogout();
    } finally {
      setUser(null);
      setOrganization(null);
      setOrganizations([]);
      setToken(null);
      setIsLoading(false);
    }
  };

  const switchOrganization = async (orgId: string) => {
    setActiveOrgId(orgId);
    await refreshProfile();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        organization,
        organizations,
        token,
        isLoading,
        login,
        register,
        logout,
        switchOrganization,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
