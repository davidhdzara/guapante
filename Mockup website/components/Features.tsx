import React from 'react';
import { FEATURES } from '../constants';

const Features: React.FC = () => {
  return (
    <section className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 pt-6">
      {FEATURES.map((feature, index) => (
        <div key={index} className="bg-white dark:bg-[#1a2e22] p-6 rounded-xl border border-[#f0f4f2] dark:border-[#2a4032] shadow-sm flex flex-col items-start gap-3 hover:shadow-md transition-shadow">
          <div className={`size-12 rounded-full ${feature.iconBgClass} ${feature.iconColorClass} flex items-center justify-center`}>
            <span className="material-symbols-outlined">{feature.icon}</span>
          </div>
          <h3 className="font-bold text-lg text-text-main dark:text-white">{feature.title}</h3>
          <p className="text-text-muted text-sm leading-relaxed">{feature.description}</p>
        </div>
      ))}
    </section>
  );
};

export default Features;