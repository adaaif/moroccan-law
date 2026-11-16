import { useParams } from 'react-router-dom';
import PlaceRoute from './PlacePage';
import PlacesPage from './PlacesPage';

/** /places and /places/<slug> from one lazy module: one import fewer in the router, the first load under its budget. */
export default function Places() {
  return useParams().place === undefined ? <PlacesPage /> : <PlaceRoute />;
}
