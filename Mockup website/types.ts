export interface Category {
  id: string;
  name: string;
  image: string;
  bgColorClass: string;
}

export interface Product {
  id: string;
  name: string;
  origin: string;
  discount?: string;
  image: string;
}

export interface Feature {
  icon: string;
  title: string;
  description: string;
  iconBgClass: string;
  iconColorClass: string;
}