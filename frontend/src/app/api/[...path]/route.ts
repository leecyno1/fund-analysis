// API proxy route - proxies all requests to backend
import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = 'http://127.0.0.1:8005/api'

function isFileDownload(contentType: string | null): boolean {
  if (!contentType) return false
  return (
    contentType.includes('csv') ||
    contentType.includes('spreadsheetml') ||
    contentType.includes('pdf') ||
    contentType.includes('octet-stream') ||
    contentType.includes('text/plain')
  )
}

async function proxyRequest(
  request: NextRequest,
  method: string,
  body?: object
): Promise<NextResponse> {
  // Remove /api prefix
  let path = request.nextUrl.pathname.replace(/^\/api/, '').replace(/^\/+/, '/')
  const searchParams = request.nextUrl.searchParams.toString()

  const fetchOptions: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
    redirect: 'follow',
  }

  if (body) {
    fetchOptions.body = JSON.stringify(body)
  } else if (method === 'POST' || method === 'PUT') {
    try {
      const text = await request.text()
      if (text) {
        fetchOptions.body = text
      }
    } catch {
      // No body to forward
    }
  }

  const tryUrl = (p: string) => `${BACKEND_URL}${p}${searchParams ? '?' + searchParams : ''}`

  console.log(`[PROXY ${method}]`, request.nextUrl.pathname, '->', tryUrl(path))

  try {
    let response = await fetch(tryUrl(path), fetchOptions)
    console.log(`[PROXY ${method}] status:`, response.status)

    // If 404, try with/without trailing slash
    if (response.status === 404) {
      const altPath = path.endsWith('/') ? path.slice(0, -1) : path + '/'
      console.log(`[PROXY ${method}] 404, retrying with:`, altPath)
      response = await fetch(tryUrl(altPath), fetchOptions)
      console.log(`[PROXY ${method}] retry status:`, response.status)
    }

    const contentType = response.headers.get('content-type')

    // Forward file downloads directly
    if (contentType && isFileDownload(contentType)) {
      const headers = new Headers()
      headers.set('content-type', contentType)
      const disposition = response.headers.get('content-disposition')
      if (disposition) {
        headers.set('content-disposition', disposition)
      }
      return new NextResponse(response.body, {
        status: response.status,
        headers,
      })
    }

    // Handle JSON responses
    let data
    if (contentType && contentType.includes('application/json')) {
      data = await response.json()
    } else {
      const text = await response.text()
      return NextResponse.json(
        { detail: text || `HTTP ${response.status}`, status: response.status },
        { status: response.status }
      )
    }

    // If backend returned an error, forward the error detail
    if (!response.ok) {
      return NextResponse.json(
        { detail: data.detail || data.message || `HTTP ${response.status}`, status: response.status },
        { status: response.status }
      )
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error(`[PROXY ${method}] error:`, error)
    const message = error instanceof Error ? error.message : 'Backend error'
    return NextResponse.json({ detail: message, status: 502 }, { status: 502 })
  }
}

export async function GET(request: NextRequest) {
  return proxyRequest(request, 'GET')
}

export async function POST(request: NextRequest) {
  let body: object | undefined
  try {
    body = await request.json()
  } catch {
    body = undefined
  }
  return proxyRequest(request, 'POST', body)
}

export async function PUT(request: NextRequest) {
  let body: object | undefined
  try {
    body = await request.json()
  } catch {
    body = undefined
  }
  return proxyRequest(request, 'PUT', body)
}

export async function DELETE(request: NextRequest) {
  return proxyRequest(request, 'DELETE')
}
