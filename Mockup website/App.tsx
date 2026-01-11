import React from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import Features from './components/Features';
import Categories from './components/Categories';
import ProductList from './components/ProductList';
import Business from './components/Business';
import Footer from './components/Footer';

const App: React.FC = () => {
  return (
    <div className="relative flex h-auto min-h-screen w-full flex-col overflow-x-hidden">
      <Header />
      <main className="flex-1 w-full max-w-[1440px] mx-auto px-4 md:px-10 py-6 md:py-8 flex flex-col gap-10 md:gap-14">
        <Hero />
        <Features />
        <Categories />
        <ProductList />
        <Business />
      </main>
      <Footer />
    </div>
  );
};

export default App;