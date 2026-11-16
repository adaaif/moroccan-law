import { createContext, useContext } from 'react';
import type { Book } from './library.api';

/** Who opens a book's card: the page that holds the sheet (`CardHost`); null where no page holds one. */
export const CardContext = createContext<((book: Book) => void) | null>(null);
export const useOpenCard = () => useContext(CardContext);
