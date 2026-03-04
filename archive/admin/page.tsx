export default function AdminPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Admin Dashboard</h1>
      <div className="grid gap-4">
        <a 
          href="/admin/blog/write" 
          className="p-4 border rounded-lg hover:bg-gray-50 transition"
        >
          <h2 className="text-xl font-semibold">Write New Blog Post</h2>
          <p className="text-gray-600">Create and publish blog content</p>
        </a>
      </div>
    </div>
  );
}