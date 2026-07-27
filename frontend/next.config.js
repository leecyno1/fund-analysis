/** @type {import('next').NextConfig} */
const nextConfig = {
  // Don't add trailing slashes - let the backend handle redirects consistently
  trailingSlash: false,
  output: 'standalone',
}

module.exports = nextConfig