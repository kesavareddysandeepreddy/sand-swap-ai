import type { UploadJobRecord } from "../../types/api";
import { formatTimestamp } from "../../utils/date";

interface UploadJobTableProps {
    jobs: UploadJobRecord[];
}

export const UploadJobTable = ({ jobs }: UploadJobTableProps) => {
    if (jobs.length === 0) {
        return <p className="memory-status">No upload jobs have been created yet.</p>;
    }

    return (
        <table className="documents-table">
            <thead>
                <tr>
                    <th>File</th>
                    <th>Size</th>
                    <th>Mime</th>
                    <th>Parser</th>
                    <th>Status</th>
                    <th>Chunks</th>
                    <th>Embeddings</th>
                    <th>Started</th>
                    <th>Completed</th>
                    <th>Error</th>
                </tr>
            </thead>
            <tbody>
                {jobs.map((job) => (
                    <tr key={job.id}>
                        <td>{job.file_name}</td>
                        <td>{job.file_size}</td>
                        <td>{job.mime_type}</td>
                        <td>{job.parser}</td>
                        <td>{job.status}</td>
                        <td>{job.chunks_created}</td>
                        <td>{job.embeddings_created}</td>
                        <td>{job.started_at ? formatTimestamp(job.started_at) : "-"}</td>
                        <td>{job.completed_at ? formatTimestamp(job.completed_at) : "-"}</td>
                        <td>{job.error ?? "-"}</td>
                    </tr>
                ))}
            </tbody>
        </table>
    );
};
