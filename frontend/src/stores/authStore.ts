import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { User } from '@/types/auth'

if (typeof window !== 'undefined') {
  localStorage.removeItem('token')
  localStorage.removeItem('auth-store')
}

interface AuthState {
  user: User | null
  token: string | null
  setAuth: (user: User, token: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    set => ({
      user: null,
      token: null,
      setAuth: (user, token) => {
        sessionStorage.setItem('token', token)
        set({ user, token })
      },
      logout: () => {
        sessionStorage.removeItem('token')
        set({ user: null, token: null })
      },
    }),
    { name: 'auth-store', storage: createJSONStorage(() => sessionStorage) }
  )
)
