import { useLocation } from 'react-router-dom';
import AiPage from './AiPage';
import ConnectPage from './ConnectPage';
import ForgotPage from './ForgotPage';
import ResetPage from './ResetPage';

const DOORS: Record<string, () => React.JSX.Element> = { '/reset': ResetPage, '/connect': ConnectPage, '/ai': AiPage };

/** The account's doors outside the account page («/forgot», «/reset», and since the MCP review «/connect» and
 *  «/ai») load together, as one route of the shell: the first load stands at its budget (3 Nov 2026). */
export default function AccountDoors() {
  const Door = DOORS[useLocation().pathname] ?? ForgotPage;
  return <Door />;
}
