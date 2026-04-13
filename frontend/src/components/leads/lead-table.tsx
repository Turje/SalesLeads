import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
} from "@tanstack/react-table";
import type { SortingState } from "@tanstack/react-table";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useUpdateStage } from "@/hooks/use-leads";
import { toast } from "sonner";
import {
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";
import type { Lead } from "@/lib/types";

const columnHelper = createColumnHelper<Lead>();

function formatCompanyType(raw: string) {
  return raw
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");
}

function formatStage(stage: string) {
  return stage.charAt(0) + stage.slice(1).toLowerCase();
}

interface LeadTableProps {
  data: Lead[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

export function LeadTable({
  data,
  total,
  page,
  pageSize,
  onPageChange,
}: LeadTableProps) {
  const navigate = useNavigate();
  const [sorting, setSorting] = useState<SortingState>([]);
  const updateStage = useUpdateStage();

  const handleApprove = (e: React.MouseEvent, leadId: number) => {
    e.stopPropagation();
    updateStage.mutate(
      { id: leadId, stage: "APPROVED" },
      {
        onSuccess: () => toast.success("Lead approved"),
        onError: () => toast.error("Failed to approve lead"),
      }
    );
  };

  const handleDisapprove = (e: React.MouseEvent, leadId: number) => {
    e.stopPropagation();
    updateStage.mutate(
      { id: leadId, stage: "DISAPPROVED" },
      {
        onSuccess: () => toast.success("Lead disapproved"),
        onError: () => toast.error("Failed to disapprove lead"),
      }
    );
  };

  const columns = useMemo(
    () => [
      columnHelper.accessor("company_name", {
        header: "Company",
        cell: (info) => (
          <button
            className="text-left font-medium text-foreground hover:underline"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/leads/${info.row.original.id}`);
            }}
          >
            {info.getValue()}
          </button>
        ),
      }),
      columnHelper.accessor("contact_name", {
        header: "Contact",
      }),
      columnHelper.accessor("company_type", {
        header: "Type",
        cell: (info) => formatCompanyType(info.getValue()),
      }),
      columnHelper.accessor("borough", {
        header: "Borough",
      }),
      columnHelper.accessor("neighborhood", {
        header: "Neighborhood",
      }),
      columnHelper.accessor("pipeline_stage", {
        header: "Stage",
        cell: (info) => {
          const stage = info.getValue();
          const variant =
            stage === "APPROVED"
              ? "default"
              : stage === "DISAPPROVED"
                ? "destructive"
                : "secondary";
          return <Badge variant={variant}>{formatStage(stage)}</Badge>;
        },
      }),
      columnHelper.display({
        id: "actions",
        header: "Actions",
        cell: (info) => {
          const lead = info.row.original;
          if (lead.pipeline_stage !== "NEW") return null;
          return (
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="xs"
                className="text-emerald-500 hover:text-emerald-400 hover:bg-emerald-500/10"
                onClick={(e) => handleApprove(e, lead.id!)}
                disabled={updateStage.isPending}
              >
                <ThumbsUp className="size-3.5" />
                Approve
              </Button>
              <Button
                variant="ghost"
                size="xs"
                className="text-red-500 hover:text-red-400 hover:bg-red-500/10"
                onClick={(e) => handleDisapprove(e, lead.id!)}
                disabled={updateStage.isPending}
              >
                <ThumbsDown className="size-3.5" />
                Reject
              </Button>
            </div>
          );
        },
        enableSorting: false,
      }),
    ],
    [navigate, updateStage.isPending]
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    manualPagination: true,
    pageCount: Math.ceil(total / pageSize),
  });

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border border-border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder ? null : (
                      <button
                        className={
                          header.column.getCanSort()
                            ? "flex items-center gap-1 hover:text-foreground"
                            : "flex items-center gap-1"
                        }
                        onClick={header.column.getToggleSortingHandler()}
                        disabled={!header.column.getCanSort()}
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                        {header.column.getCanSort() && (
                          <ArrowUpDown className="size-3 text-muted-foreground" />
                        )}
                      </button>
                    )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-muted-foreground"
                >
                  No leads found.
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/leads/${row.original.id}`)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          Page {page} of {totalPages || 1} ({total} leads)
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
          >
            <ChevronLeft className="size-4" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
          >
            Next
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
