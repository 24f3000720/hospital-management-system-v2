function buildHeaders(headers = {}, hasJsonBody = false) {
  const nextHeaders = { ...headers }

  if (hasJsonBody && !nextHeaders['Content-Type']) {
    nextHeaders['Content-Type'] = 'application/json'
  }

  return nextHeaders
}

export async function apiRequest(path, options = {}) {
  const {
    method = 'GET',
    data,
    headers,
    ...rest
  } = options

  const hasJsonBody = data !== undefined && method !== 'GET'

  const response = await fetch(path, {
    method,
    credentials: 'include',
    headers: buildHeaders(headers, hasJsonBody),
    body: hasJsonBody ? JSON.stringify(data) : undefined,
    ...rest,
  })

  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json')
    ? await response.json()
    : null

  if (!response.ok) {
    const error = new Error(payload?.message || `Request failed with status ${response.status}`)
    error.status = response.status
    error.payload = payload
    throw error
  }

  return payload
}
