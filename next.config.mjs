/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  // Rewrites enable local proxying to Flask during `next dev`.
  // Note: During `next build` (output: 'export'), static export omits rewrites;
  // in production, client requests use NEXT_PUBLIC_API_URL directly.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:5000/api/:path*',
      },
    ]
  },
}

export default nextConfig
