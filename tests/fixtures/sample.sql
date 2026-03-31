create table customers
(
    cust_id   varchar(12)  not null,
    cust_nm   varchar(100) not null,
    rgst_dt   timestamp
);

comment on table customers is '고객정보';
comment on column customers.cust_id is '고객ID';
comment on column customers.cust_nm is '고객명';
comment on column customers.rgst_dt is '등록일시';

create unique index customers_pk
    on customers (cust_id);

alter table customers
    add constraint customers_pkey
        primary key (cust_id);

create table orders
(
    order_id  integer      not null,
    cust_id   varchar(12)  not null,
    status    varchar(20),
    order_dt  timestamp
);

comment on table orders is '주문정보';
comment on column orders.order_id is '주문ID';
comment on column orders.cust_id is '고객ID';
comment on column orders.status is '주문상태';
comment on column orders.order_dt is '주문일시';

create index orders_cust_idx
    on orders (cust_id);

alter table orders
    add constraint orders_pkey
        primary key (order_id);

alter table orders
    add constraint orders_cust_fk
        foreign key (cust_id) references customers;
