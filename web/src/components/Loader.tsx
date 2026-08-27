import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export function AppLoader() {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 2 second artificial load time for cinematic effect
    const timer = setTimeout(() => setLoading(false), 2000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <AnimatePresence>
      {loading && (
        <motion.div
          key="global-loader"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.8, ease: "easeInOut" }}
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-[#050505]"
        >
          {/* Rotating geometry for a high-tech vibe */}
          <motion.div
            animate={{ 
              scale: [1, 1.2, 1], 
              rotate: [0, 180, 360] 
            }}
            transition={{ 
              duration: 2, 
              repeat: Infinity, 
              ease: "easeInOut" 
            }}
            className="w-16 h-16 border-2 border-white border-t-transparent border-b-transparent rounded-full mb-8 relative flex items-center justify-center"
          >
            <motion.div 
              animate={{ rotate: [360, 0] }}
              transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
              className="w-8 h-8 border-2 border-zinc-500 border-l-transparent border-r-transparent rounded-full"
            />
          </motion.div>
          
          <motion.h2
            initial={{ opacity: 0, letterSpacing: "0em" }}
            animate={{ opacity: 1, letterSpacing: "0.4em" }}
            transition={{ duration: 1.5, ease: "easeOut" }}
            className="text-white font-black uppercase text-sm"
          >
            LUNA DRISHTI
          </motion.h2>
          
          
        </motion.div>
      )}
    </AnimatePresence>
  );
}
