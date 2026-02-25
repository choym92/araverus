import { requireUser } from '@/lib/authz';
import DashboardClient from './DashboardClient';

export default async function DashboardPage() {
  await requireUser(); // Redirects to /login if not authenticated

  return <DashboardClient />;
}
