import React from 'react';
import { CATEGORIES } from '../constants';

const Categories: React.FC = () => {
  return (
    <section>
      <div className="flex items-end justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-text-main dark:text-white">Categorías Principales</h2>
          <p className="text-text-muted text-sm mt-1">Explora nuestra variedad de productos.</p>
        </div>
        <a className="text-primary font-bold text-sm hover:underline flex items-center gap-1" href="#">
          Ver todas <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
        </a>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {CATEGORIES.map((cat) => (
          <a key={cat.id} href="#" className="group flex flex-col items-center gap-3 p-4 rounded-xl bg-white dark:bg-[#1a2e22] border border-[#f0f4f2] dark:border-[#2a4032] hover:border-primary/50 transition-all hover:shadow-md">
            <div className={`size-20 rounded-full ${cat.bgColorClass} flex items-center justify-center overflow-hidden`}>
              <img 
                alt={cat.name} 
                className="w-full h-full object-cover group-hover:scale-110 transition-transform" 
                src={cat.image} 
              />
            </div>
            <span className="font-semibold text-sm group-hover:text-primary transition-colors text-text-main dark:text-white">{cat.name}</span>
          </a>
        ))}
      </div>
    </section>
  );
};

export default Categories;