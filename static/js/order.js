function loadOrders() {
    $.get('/get_orders', function(data) {
        $('#orders-table').DataTable({
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
                { data: 'subtotal' },
                { data: 'shipping' },
                { data: 'total' },
                { data: 'discount_code' },
                { data: 'discount_amount' },
                { data: 'cod_amount' },
                { data: 'advance_delivery_charges' },
                { data: 'courier' },
                { data: 'shipping_status' },
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
                },
                {
                    data: null,
                    orderable: false,
                    render: function (data, type, row) {
                        return `
                            <button class="btn btn-sm btn-warning edit-btn" data-id="${row.id}">Edit</button>
                            <button class="btn btn-sm btn-danger delete-btn" data-id="${row.id}">Delete</button>
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

                    if (index === 16) {
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
                    } else {
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

    // Only one dropdown open at a time
    $(document).on('select2:opening', '.status-select', function (e) {
        $('.status-select').not(this).each(function () {
            if ($(this).data('select2')) {
                $(this).select2('close');
            }
        });
    });

    // Edit modal
    $(document).on('click', '.edit-btn', function () {
        let id = $(this).data('id');
        $.get(`/order/${id}`, function (order) {
            $('#edit-id').val(order.id);
            $('#edit-item').val(order.item_name);
            $('#edit-status').val(order.status);
            $('#edit-city').val(order.billing_city);
            $('#edit-order-number').val(order.order_number);
            $('#editModal').modal('show');
        });
    });

    $('#save-edit').click(function() {
        let id = $('#edit-id').val();
        $.ajax({
            url: `/order/${id}`,
            type: 'PUT',
            contentType: 'application/json',
            data: JSON.stringify({
                item_name: $('#edit-item').val(),
                status: $('#edit-status').val(),
                billing_city: $('#edit-city').val(),
                order_source: "Shopify",
                order_number: $('#edit-order-number').val(),
                subtotal: 0,
                shipping: 0,
                discount_code: "",
                discount_amount: 0,
                created_at: "2025-01-01 00:00:00",
                quantity: 1,
                billing_name: "",
                billing_phone: "",
                billing_street: "",
                advance_delivery_charges: "",
                cod_amount: 0,
                courier: "",
                shipping_status: ""
            }),
            success: () => {
                $('#editModal').modal('hide');
                loadOrders();
            }
        });
    });

    $(document).on('click', '.delete-btn', function () {
        let id = $(this).data('id');
        if (confirm("Delete this order?")) {
            $.ajax({ url: `/order/${id}`, type: 'DELETE' }).done(() => loadOrders());
        }
    });

    $('#csvForm').submit(function(e) {
        e.preventDefault();
        let formData = new FormData(this);
        $.ajax({
            url: '/import',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: () => {
                alert('CSV Imported');
                location.reload();
            },
            error: () => alert('Import failed')
        });
    });
});
