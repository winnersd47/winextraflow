import { NextRequest, NextResponse } from 'next/server'

const PUBLIC_PATHS = [
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
  '/',
  '/terms',
  '/privacy',
  '/refund',
  '/cookies',
  '/api/v1/auth',
  '/api/v1/public',
]

const PREMIUM_PATHS = [
  '/dashboard/strategies/create',
  '/dashboard/copy-trading',
  '/dashboard/execution',
  '/dashboard/backtesting',
]

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some(p => pathname === p || pathname.startsWith(p + '/'))
}

function isPremiumRoute(pathname: string): boolean {
  return PREMIUM_PATHS.some(p => pathname.startsWith(p))
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  const token = request.cookies.get('access_token')?.value

  // Публичные маршруты — пропускаем
  if (isPublic(pathname)) {
    // Если авторизован и зашёл на /login или /register — редирект в dashboard
    if (token && (pathname === '/login' || pathname === '/register')) {
      return NextResponse.redirect(new URL('/dashboard', request.url))
    }
    return NextResponse.next()
  }

  // Нет токена — редирект на /login
  if (!token) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('next', pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|icons|images).*)',
  ],
}
