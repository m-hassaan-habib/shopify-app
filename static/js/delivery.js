function loadOrders() {
    $.get('/get_orders', function(data) {
        $('#delivery-table').DataTable({
            destroy: true,
            data: data,
            columns: [
                { data: 'id' },
                { data: 'order_number' },
                { data: 'item_name' },
                { data: 'billing_name' },
                { data: 'billing_phone' },
                { data: 'billing_street' },
                { data: 'billing_city' },
                { data: 'cod_amount' },
                {
                    data: 'courier',
                    render: function (data, type, row) {
                        return `
                            <select class="courier-select form-control form-select-sm" data-id="${row.id}">
                                <option ${data === 'Daewoo' ? 'selected' : ''}>Daewoo</option>
                                <option ${data === 'Daraz' ? 'selected' : ''}>Daraz</option>
                            </select>
                        `;
                    }
                },
                {
                    data: 'shipping_status',
                    render: function (data, type, row) {
                        return `
                            <select class="shipping_status-select form-control form-select-sm" data-id="${row.id}">
                                <option ${data === 'Shipped' ? 'selected' : ''}>Shipped</option>
                                <option ${data === 'To Process' ? 'selected' : ''}>To Process</option>
                            </select>
                        `;
                    }
                },
                {
                    data: 'status',
                    render: function (data, type, row) {
                        return `
                            <select class="status-select form-control form-select-sm" data-id="${row.id}">
                                <option ${data === 'Confirmed' ? 'selected' : ''}>Confirmed</option>
                                <option ${data === 'Pending' ? 'selected' : ''}>Pending</option>
                                <option ${data === 'Cancelled' ? 'selected' : ''}>Cancelled</option>
                                <option ${data === 'Not Responding' ? 'selected' : ''}>Not Responding</option>
                                <option ${data === 'To Process' ? 'selected' : ''}>To Process</option>
                            </select>
                        `;
                    }
                }
            ],
            orderCellsTop: true,
            fixedHeader: true,
            initComplete: function () {
                let api = this.api();
                api.columns().every(function (index) {
                    const header = $('thead tr.filters th').eq(index);

                    if (index === 10) {
                        const select = $('<select class="form-control form-select-sm status-filter"><option value="">All</option></select>')
                            .appendTo(header.empty())
                            .on('change', function () {
                                api.column(index).search(this.value).draw();
                            });

                        this.data().unique().sort().each(function (d) {
                            if (d) select.append(`<option value="${d}">${d}</option>`);
                        });

                        select.select2({
                            placeholder: 'Search status',
                            width: '100%',
                            minimumResultsForSearch: Infinity
                        });
                    } 
                    else if (index === 9) {
                        // shipping_status filter
                        const select = $('<select class="form-control form-select-sm shipping-status-filter"><option value="">All</option></select>')
                            .appendTo(header.empty())
                            .on('change', function () {
                                api.column(index).search(this.value).draw();
                            });

                        this.data().unique().sort().each(function (d) {
                            if (d) select.append(`<option value="${d}">${d}</option>`);
                        });

                        select.select2({
                            placeholder: 'Shipping Status',
                            width: '100%',
                            minimumResultsForSearch: Infinity
                        });
                    } 
                    else if (index === 8) {
                        // shipping_status filter
                        const select = $('<select class="form-control form-select-sm courier-filter"><option value="">All</option></select>')
                            .appendTo(header.empty())
                            .on('change', function () {
                                api.column(index).search(this.value).draw();
                            });

                        this.data().unique().sort().each(function (d) {
                            if (d) select.append(`<option value="${d}">${d}</option>`);
                        });

                        select.select2({
                            placeholder: 'Courier',
                            width: '100%',
                            minimumResultsForSearch: Infinity
                        });
                    } 
                    else {
                        const input = header.find('input');
                        if (input.length) {
                            input.on('keyup change', function () {
                                api.column(index).search(this.value).draw();
                            });
                        }
                    }
                });

                // Initialize select2 on status columns
                $('.status-select').select2({
                    minimumResultsForSearch: -1,
                    width: '100%',
                    dropdownAutoWidth: true
                });
            }
        });
    });
}

$(document).ready(function() {
    loadOrders();

    $(document).on('change', '.status-select', function () {
        let select = $(this);
        let id = select.data('id');
        let newStatus = select.val();

        $.ajax({
            url: `/order/${id}/status`,
            type: 'PATCH',
            contentType: 'application/json',
            data: JSON.stringify({ status: newStatus }),
            success: () => {
                select.addClass('border-success');
                setTimeout(() => select.removeClass('border-success'), 1000);
            },
            error: () => {
                select.addClass('border-danger');
                setTimeout(() => select.removeClass('border-danger'), 1000);
            }
        });
    });


    $(document).on('change', '.shipping_status-select', function () {
        let select = $(this);
        let id = select.data('id');
        let newShippingStatus = select.val();
    
        $.ajax({
            url: `/order/${id}/shipping_status`,
            type: 'PATCH',
            contentType: 'application/json',
            data: JSON.stringify({ shipping_status: newShippingStatus }),
            success: () => {
                select.addClass('border-success');
                setTimeout(() => select.removeClass('border-success'), 1000);
            },
            error: () => {
                select.addClass('border-danger');
                setTimeout(() => select.removeClass('border-danger'), 1000);
            }
        });
    });

    $(document).on('change', '.courier-select', function () {
        let select = $(this);
        let id = select.data('id');
        let courier = select.val();
    
        $.ajax({
            url: `/order/${id}/courier`,
            type: 'PATCH',
            contentType: 'application/json',
            data: JSON.stringify({ courier: courier }),
            success: () => {
                select.addClass('border-success');
                setTimeout(() => select.removeClass('border-success'), 1000);
            },
            error: () => {
                select.addClass('border-danger');
                setTimeout(() => select.removeClass('border-danger'), 1000);
            }
        });
    });

    
    $(document).on('select2:opening', '.status-select, .shipping-status-select, .courier', function (e) {
        $('.status-select, .shipping-status-select').not(this).each(function () {
            if ($(this).data('select2')) {
                $(this).select2('close');
            }
        });
    });
});
