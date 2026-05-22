/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        // Use 127.0.0.1 (IPv4), not "localhost": on macOS localhost resolves to
        // IPv6 ::1 first, which can collide with other Docker services bound to :8000.
        destination: `${process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
