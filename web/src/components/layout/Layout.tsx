import { Outlet, useLocation } from 'react-router-dom';
import { Navbar } from './Navbar';
import { WorkspaceNav } from './WorkspaceNav';
import { Footer } from './Footer';
import { AppLoader } from '../Loader';

export function Layout() {
  const location = useLocation();
  const isLanding = location.pathname === '/';

  return (
    <div className="min-h-screen flex flex-col bg-[#050505] text-zinc-300 selection:bg-white/20 selection:text-zinc-300 font-sans">
      <AppLoader />
      <Navbar />
      {!isLanding && <WorkspaceNav />}
      
      <main className="flex-grow flex flex-col relative min-w-0">
        {/* Subtle, highly professional grid background */}
        {!isLanding && <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />}
        
        <div className="relative flex-grow flex flex-col min-w-0">
          <Outlet />
        </div>
      </main>
      {!isLanding && <Footer />}
    </div>
  );
}
