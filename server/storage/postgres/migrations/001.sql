ALTER TABLE public.vcons RENAME COLUMN "type" TO created_by_local_type;
ALTER TABLE public.vcons ADD created_by_domain text NULL;
ALTER TABLE public.vcons ADD created_by_local_type_version text NULL;
